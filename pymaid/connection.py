__all__ = ['Connection']

import time
import struct

from gevent.greenlet import Greenlet
from gevent.queue import Queue
from gevent import socket
from gevent.core import READ, WRITE, EVENTS

from google.protobuf.message import DecodeError

from pymaid.agent import ServiceAgent
from pymaid.apps.monitor import MonitorService_Stub
from pymaid.parser import pack_packet, unpack_packet, RESPONSE
from pymaid.utils import pymaid_logger_wrapper
from pymaid.error import (
    BaseError, BaseMeta, HeartbeatTimeout, PacketTooLarge, EOF
)
from pymaid.pb.pymaid_pb2 import ErrorMessage


@pymaid_logger_wrapper
class Connection(object):

    HEADER = '!BH'
    HEADER_LENGTH = struct.calcsize(HEADER)
    LINGER_PACK = struct.pack('ii', 1, 0)

    HEADER_STRUCT = struct.Struct(HEADER)
    pack_header = HEADER_STRUCT.pack
    unpack_header = HEADER_STRUCT.unpack

    MAX_SEND = 5
    MAX_PACKET_LENGTH = 8 * 1024

    CONN_ID = 1

    __slots__ = [
        'channel', 'server_side', 'conn_id', 'peername', 'sockname',
        'is_closed', 'close_cb',
        'buffers', 'transmissions', 'transmission_id',
        'need_heartbeat', 'heartbeat_interval', 'last_check_heartbeat',
        '_heartbeat_timeout_counter', '_max_heartbeat_timeout_count',
        '_socket', '_send_queue', '_recv_queue', '_socket_watcher',
        '_monitor_agent',
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
        self._monitor_agent = None
        self.need_heartbeat = 0

        self.conn_id = self.CONN_ID
        Connection.CONN_ID += 1

        self.buffers = []
        self.transmissions = {}
        self._send_queue = Queue()
        self._recv_queue = Queue()

        self._socket_watcher = self.channel.loop.io(sock.fileno(), READ)
        self._socket_watcher.start(self._io_loop, pass_events=True)

    def _setsockopt(self, sock):
        sock.setblocking(0)
        sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, self.LINGER_PACK)

    def setsockopt(self, *args, **kwargs):
        self._socket.setsockopt(*args, **kwargs)

    def setup_server_heartbeat(self, max_heartbeat_timeout_count):
        assert max_heartbeat_timeout_count >= 1
        self._heartbeat_timeout_counter = 0
        self._max_heartbeat_timeout_count = max_heartbeat_timeout_count
        self.last_check_heartbeat = time.time()

    def setup_client_heartbeat(self, channel):
        self._monitor_agent = ServiceAgent(MonitorService_Stub(channel), self)
        resp = self._monitor_agent.get_heartbeat_info()

        if not resp.need_heartbeat:
            return

        self.need_heartbeat = 1
        self.heartbeat_interval = resp.heartbeat_interval
        self.last_check_heartbeat = time.time()
        channel.add_notify_heartbeat_conn(self.conn_id)

    def clear_heartbeat_counter(self):
        self.last_check_heartbeat = time.time()
        self._heartbeat_timeout_counter = 0

    def heartbeat_timeout(self):
        self._heartbeat_timeout_counter += 1
        if self._heartbeat_timeout_counter >= self._max_heartbeat_timeout_count:
            self.close(HeartbeatTimeout(host=self.sockname, peer=self.peername))

    def notify_heartbeat(self):
        self._monitor_agent.notify_heartbeat()

    def send(self, controller):
        assert controller
        parser_type = controller.parser_type
        packet_buffer = pack_packet(controller.meta, parser_type)
        self._send_queue.put(
            self.pack_header(parser_type, len(packet_buffer)) +
            packet_buffer +
            controller.content
        )
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
            self.logger.error(
                '[host|%s][peer|%s] closed with reason: %s',
                self.sockname, self.peername, reason
            )
        else:
            self.logger.info(
                '[host|%s][peer|%s] closed cleanly', self.sockname, self.peername
            )

        if self._monitor_agent:
            self._monitor_agent.close()

        self._send_queue.queue.clear()
        self._recv_queue.queue.clear()
        self._recv_queue.put(None)
        self._socket_watcher.stop()
        self._socket.close()
        del self.buffers[:]

        if self.close_cb:
            self.close_cb(self, reason)
        self.close_cb = None

    def set_close_cb(self, close_cb):
        assert not self.close_cb
        assert callable(close_cb)
        self.close_cb = close_cb
    
    def _io_loop(self, event):
        if event & READ:
            self._handle_recv()
        if event & WRITE:
            self._handle_send()

    def _handle_send(self):
        qsize = self._send_queue.qsize()
        if not qsize: 
            return

        try:
            for _ in xrange(min(qsize, self.MAX_SEND)):
                buffers = self._send_queue.get()
                if not buffers:
                    break

                # see pydoc of socket.send
                self._socket.send(memoryview(buffers))
        except socket.error as ex:
            if ex.args[0] == socket.EWOULDBLOCK:
                self._send_queue.queue.appendleft(buffers)
                return
            self.close(ex)

    def _recv_n(self, nbytes):
        buffers = []
        recv, append, length = self._socket.recv, buffers.append, 0
        try:
            while length < nbytes:
                t = recv(nbytes - length)
                if not t:
                    raise EOF()
                append(t)
                length += len(t)
        except socket.error as ex:
            if ex.args[0] == socket.EWOULDBLOCK:
                ret = ''.join(buffers)
            else:
                raise
        else:
            ret = ''.join(buffers)
        return ret

    def _handle_recv(self):
        unpack_header, header_length = self.unpack_header, self.HEADER_LENGTH

        # receive header
        buffers_size = sum(map(len, self.buffers))
        try:
            if buffers_size < header_length:
                remain = header_length - buffers_size
                buf = self._recv_n(remain)

                self.buffers.append(buf)
                if len(buf) < remain:
                    # received data not enough
                    return

            buffers = ''.join(self.buffers)
            buffers_size = len(buffers)
            header = buffers[:header_length]
            assert len(header) == header_length
            parser_type, packet_length = unpack_header(header)
            if packet_length >= self.MAX_PACKET_LENGTH:
                self.close(PacketTooLarge(packet_length=packet_length))
                return

            controller_length = header_length + packet_length
            if buffers_size < controller_length:
                remain = controller_length - buffers_size
                buf = self._recv_n(remain)

                self.buffers.append(buf)
                if len(buf) < remain:
                    # received data not enough
                    return
                else:
                    buffers += buf

            buffers_size = len(buffers)
            assert buffers_size >= controller_length
            packet_buffer = buffers[header_length:controller_length]

            controller = unpack_packet(packet_buffer, parser_type)

            meta = controller.meta
            if meta.content_size:
                content_length = controller_length + meta.content_size
                if buffers_size < content_length:
                    remain = content_length - buffers_size
                    buf = self._recv_n(remain)

                    if len(buf) < remain:
                        # received data not enough
                        self.buffers.append(buf)
                        return
                    else:
                        controller.content = (
                            buffers[controller_length:content_length] + buf
                        )

            if meta.packet_type == RESPONSE:
                self._handle_response(controller)
            else:
                controller.parser_type = parser_type
                self._recv_queue.put(controller)
            del self.buffers[:]
        except Exception as ex:
            self.close(ex)

    def _handle_response(self, controller):
        transmission_id = controller.meta.transmission_id
        assert transmission_id in self.transmissions
        async_result = self.transmissions.pop(transmission_id)

        if controller.Failed():
            error_message = ErrorMessage()
            error_message.ParseFromString(controller.content)
            ex = BaseMeta.get_by_code(error_message.error_code)()
            ex.message = error_message.error_message
            async_result.set_exception(ex)
        else:
            response = self.channel.get_stub_response_class(controller.meta)()
            try:
                response.ParseFromString(controller.content)
            except DecodeError as ex:
                async_result.set_exception(ex)
            else:
                async_result.set(response)
