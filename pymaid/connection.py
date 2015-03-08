__all__ = ['Connection']

import time
import struct
import six

from gevent.greenlet import Greenlet
from gevent.queue import Queue
from gevent import socket
from gevent.core import READ, WRITE, EVENTS

from google.protobuf.message import DecodeError

from pymaid.controller import Controller
from pymaid.parser import (
    unpack_header, HEADER_LENGTH, REQUEST, RESPONSE, NOTIFICATION
)
from pymaid.utils import greenlet_pool, pymaid_logger_wrapper
from pymaid.error import (
    BaseError, BaseMeta, HeartbeatTimeout, PacketTooLarge, EOF
)
from pymaid.pb.pymaid_pb2 import ErrorMessage

range = six.moves.range
error, EWOULDBLOCK = socket.error, socket.EWOULDBLOCK


@pymaid_logger_wrapper
class Connection(object):

    LINGER_PACK = struct.pack('ii', 1, 0)

    MAX_SEND = 5
    MAX_PACKET_LENGTH = 8 * 1024

    CONN_ID = 1

    __slots__ = [
        'channel', 'server_side', 'conn_id', 'peername', 'sockname',
        'is_closed', 'close_cb', 'transmissions', 'transmission_id',
        'need_heartbeat', 'heartbeat_interval', 'last_check_heartbeat',
        '_heartbeat_timeout_counter', '_max_heartbeat_timeout_count',
        '_socket', '_send_queue', '_recv_queue', '_socket_watcher',
        '_header_buffers', '_header_buffers_size',
        '_controller_buffers', '_controller_buffers_size',
        '_content_buffers', '_content_buffers_size'
    ]

    def __init__(self, channel, sock, server_side):
        self.channel = channel
        self.server_side = server_side
        self.transmission_id = 1

        self._setsockopt(sock)
        self._socket = sock
        self.peername = sock.getpeername()
        self.sockname = sock.getsockname()

        self.is_closed = False
        self.close_cb = None
        self.need_heartbeat = 0

        self.conn_id = self.CONN_ID
        Connection.CONN_ID += 1

        self._header_buffers = memoryview(bytearray(HEADER_LENGTH))
        self._header_buffers_size = 0
        self._controller_buffers, self._controller_buffers_size = None, 0
        self._content_buffers, self._content_buffers_size = None, 0
        self.transmissions = {}
        self._send_queue = Queue()
        self._recv_queue = Queue()

        self._socket_watcher = self.channel.loop.io(sock.fileno(), READ)
        self._socket_watcher.start(self._io_loop, pass_events=True)
        greenlet_pool.spawn(self._handle_packet)

    def _setsockopt(self, sock):
        sock.setblocking(0)
        sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, self.LINGER_PACK)

    def _io_loop(self, event):
        if event & READ:
            self._handle_recv()
        if event & WRITE:
            self._handle_send()

    def _handle_send(self):
        send_queue = self._send_queue
        qsize = send_queue.qsize()
        if not qsize: 
            return

        get_buf, send = send_queue.get, self._socket.send
        try:
            for _ in range(min(qsize, self.MAX_SEND)):
                buffers = get_buf()
                if not buffers:
                    break

                # see pydoc of socket.send
                sent, buffers_size = 0, len(buffers)
                buffers = memoryview(buffers)
                while sent < buffers_size:
                    sent += send(buffers[sent:])
        except error as ex:
            if ex.args[0] == EWOULDBLOCK:
                send_queue.queue.appendleft(buffers[sent:])
                self._socket_watcher.feed(WRITE, self._io_loop, EVENTS)
                return
            self.close(ex, reset=True)

    def _recv_n(self, buffers, nbytes):
        recv_into, length = self._socket.recv_into, 0
        try:
            while length < nbytes:
                t = recv_into(buffers[length:])
                if not t:
                    raise EOF()
                length += t
        except error as ex:
            if ex.args[0] == EWOULDBLOCK:
                ret = length
            else:
                raise
        else:
            ret = length
        return ret

    def _handle_recv(self):
        header_length = HEADER_LENGTH

        # receive header
        header_buf = self._header_buffers
        header_buf_size = self._header_buffers_size
        try:
            if header_buf_size < header_length:
                remain = header_length - header_buf_size
                received = self._recv_n(header_buf[header_buf_size:], remain)
                self._header_buffers_size += received
                if received < remain:
                    # received data not enough
                    return

            parser_type, packet_length = unpack_header(header_buf.tobytes())
            if packet_length >= self.MAX_PACKET_LENGTH:
                self.close(PacketTooLarge(packet_length=packet_length))
                return

            controller_buf_size = self._controller_buffers_size
            if not controller_buf_size:
                self._controller_buffers = memoryview(bytearray(packet_length))
            controller_buf = self._controller_buffers
            if controller_buf_size < packet_length:
                remain = packet_length - controller_buf_size
                received = self._recv_n(
                    controller_buf[controller_buf_size:], remain
                )
                self._controller_buffers_size += received
                if received < remain:
                    # received data not enough
                    return

            controller = Controller.unpack_packet(
                controller_buf.tobytes(), parser_type
            )

            content_size = controller.meta.content_size
            if content_size:
                content_buf_size = self._content_buffers_size
                if not content_buf_size:
                    self._content_buffers = memoryview(bytearray(content_size))
                content_buf = self._content_buffers
                if content_buf_size < content_size:
                    remain = content_size - controller_buf_size
                    received = self._recv_n(
                        content_buf[content_buf_size:], remain
                    )
                    self._content_buffers_size += received
                    if received < remain:
                        # received data not enough
                        return
                    controller.content = content_buf.tobytes()

            if controller.meta.packet_type == RESPONSE:
                self._handle_response(controller)
            else:
                self._recv_queue.put(controller)
            self._header_buffers_size = self._controller_buffers_size = 0
            self._content_buffers_size = 0
            self._controller_buffers = self._content_buffers = None
        except error as ex:
            self.close(ex, reset=True)
        except Exception as ex:
            self.close(ex)

    def _handle_packet(self):
        recv, reason = self.recv, None
        callbacks = {
            REQUEST: self.channel.handle_request,
            NOTIFICATION: self.channel.handle_notification,
        }
        try:
            while 1:
                controller = recv()
                if not controller:
                    break
                controller.conn = self
                callbacks[controller.meta.packet_type](self, controller)
        except Exception as ex:
            reason = ex
        finally:
            self.close(reason)

    def _handle_response(self, controller):
        transmission_id = controller.meta.transmission_id
        assert transmission_id in self.transmissions
        async_result = self.transmissions.pop(transmission_id)

        if controller.Failed():
            error_message = controller.unpack_content(ErrorMessage)
            ex = BaseMeta.get_by_code(error_message.error_code)()
            ex.message = error_message.error_message
            async_result.set_exception(ex)
        else:
            response_cls = self.channel.get_stub_response_class(controller.meta)
            try:
                async_result.set(controller.unpack_content(response_cls))
            except DecodeError as ex:
                async_result.set_exception(ex)

    def setsockopt(self, *args, **kwargs):
        self._socket.setsockopt(*args, **kwargs)

    def setup_server_heartbeat(self, max_heartbeat_timeout_count):
        assert max_heartbeat_timeout_count >= 1
        self._heartbeat_timeout_counter = 0
        self._max_heartbeat_timeout_count = max_heartbeat_timeout_count
        self.last_check_heartbeat = time.time()

    def setup_client_heartbeat(self, heartbeat_interval):
        assert heartbeat_interval >= 0
        self.need_heartbeat = 1
        self.heartbeat_interval = heartbeat_interval
        self.last_check_heartbeat = time.time()

    def clear_heartbeat_counter(self):
        self.last_check_heartbeat = time.time()
        self._heartbeat_timeout_counter = 0

    def heartbeat_timeout(self):
        self._heartbeat_timeout_counter += 1
        if self._heartbeat_timeout_counter >= self._max_heartbeat_timeout_count:
            self.close(HeartbeatTimeout(host=self.sockname, peer=self.peername))

    def send(self, packet_buffer):
        assert packet_buffer
        self._send_queue.put(packet_buffer)
        # add WRITE event for once
        self._socket_watcher.feed(WRITE, self._io_loop, EVENTS)

    def recv(self, timeout=None):
        return self._recv_queue.get(timeout=timeout)

    def close(self, reason=None, reset=False):
        if self.is_closed:
            return
        self.is_closed = True

        if isinstance(reason, Greenlet):
            reason = reason.exception

        if reason:
            if reset or isinstance(reason, BaseError):
                self.logger.error(
                    '[host|%s][peer|%s] closed with reason: %s',
                    self.sockname, self.peername, reason
                )
            else:
                self.logger.exception(
                    '[host|%s][peer|%s] closed with reason: %s',
                    self.sockname, self.peername, reason
                )
        else:
            self.logger.info(
                '[host|%s][peer|%s] closed cleanly', self.sockname, self.peername
            )

        self._send_queue.queue.clear()
        self._recv_queue.queue.clear()
        self._recv_queue.put(None)
        self._socket_watcher.stop()
        self._socket.close()
        self._header_buffers = self._controller_buffers = None
        self._content_buffers = None

        if self.close_cb:
            self.close_cb(self, reason)
        self.close_cb = None

    def set_close_cb(self, close_cb):
        assert not self.close_cb
        assert callable(close_cb)
        self.close_cb = close_cb
