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
from pymaid.parser import get_parser, REQUEST
from pymaid.utils import pymaid_logger_wrapper
from pymaid.error import BaseMeta, HeartbeatTimeout
from pymaid.pb.pymaid_pb2 import ErrorMessage


@pymaid_logger_wrapper
class Connection(object):

    HEADER = '!2BI'
    HEADER_LENGTH = struct.calcsize(HEADER)
    LINGER_PACK = struct.pack('ii', 1, 0)

    HEADER_STRUCT = struct.Struct(HEADER)

    # see /proc/sys/net/core/rmem_default and /proc/sys/net/core/rmem_max
    # the doubled value is max size for one socket recv call
    # you need to ensure *MAX_RECV* times *MAX_PACKET_LENGTH* is lower than that
    # in some situation, the basic value is something like 212992
    # so MAX_RECV * MAX_PACKET_LENGTH = 24576 < 212992 is ok here
    MAX_SEND = 5
    MAX_RECV = 3
    MAX_PACKET_LENGTH = 8 * 1024
    RCVBUF = MAX_RECV * MAX_PACKET_LENGTH

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
        # system will doubled this buffer
        #sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.RCVBUF/2)

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
        parser_type, packet_type = controller.parser_type, controller.packet_type
        packet_buffer = get_parser(parser_type).pack_packet(controller)
        self._send_queue.put((parser_type, packet_type, packet_buffer))
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
            self.logger.warn(
                '[host|%s][peer|%s] closed with reason: %s',
                self.sockname, self.peername, repr(reason)
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

        pack_header = self.HEADER_STRUCT.pack
        try:
            for _ in xrange(min(qsize, self.MAX_SEND)):
                controller = self._send_queue.get()
                if not controller:
                    break
                parser_type, packet_type, packet_buffer = controller

                # see pydoc of socket.sendall
                self._socket.sendall(
                    pack_header(parser_type, packet_type, len(packet_buffer)) +
                    packet_buffer
                )
        except socket.error as ex:
            if ex.args[0] == socket.EWOULDBLOCK:
                return
            self.close(ex)

    def _recv_n(self, nbytes):
        recv, append, length = self._socket.recv, self.buffers.append, 0
        try:
            while length < nbytes:
                t = recv(nbytes - length)
                if not t:
                    ret = 0
                    break
                append(t)
                length += len(t)
        except socket.error as ex:
            if ex.args[0] == socket.EWOULDBLOCK:
                ret = length
            else:
                ret = ex
        except Exception as ex:
            ret = ex
        else:
            ret = length
        return ret

    def _handle_recv(self):
        length = self._recv_n(self.RCVBUF)

        # handle all received data even if receive EOF or catch exception
        buffers = ''.join(self.buffers)
        current, buffers_length = 0, len(buffers)
        unpack_header, header_length = self.HEADER_STRUCT.unpack, self.HEADER_LENGTH
        while current < buffers_length:
            handled = current
            header = buffers[handled:handled+header_length]
            if len(header) < header_length:
                break
            handled += header_length

            parser_type, packet_type, packet_length = unpack_header(header)
            if packet_length >= self.MAX_PACKET_LENGTH:
                self.close('[packet_length|%d] out of limitation' % packet_length)
                break

            packet_buffer = buffers[handled:handled+packet_length]
            if len(packet_buffer) < packet_length:
                break

            controller = get_parser(parser_type).unpack_packet(packet_buffer)
            if packet_type == REQUEST:
                controller.set_parser_type(parser_type)
                self._recv_queue.put(controller)
            else:
                # now we have REQUEST/RESPONSE two packet_type
                self._handle_response(controller)
            current = handled + packet_length

        del self.buffers[:]
        if current < buffers_length and not self.is_closed:
            self.buffers.append(buffers[current:])

        # close if receive EOF or catch exception
        if not length:
            self.close('has received EOF', reset=True)
        elif not isinstance(length, (int, long)):
            # exception
            self.close(length, reset=True)

    def _handle_response(self, controller):
        transmission_id = controller.transmission_id
        assert transmission_id in self.transmissions
        async_result = self.transmissions.pop(transmission_id)

        if controller.Failed():
            error_message = ErrorMessage()
            error_message.ParseFromString(controller.message)
            ex = BaseMeta.get_by_code(error_message.error_code)()
            ex.message = error_message.error_message
            async_result.set_exception(ex)
        else:
            response = self.channel.get_stub_response_class(controller)()
            try:
                response.ParseFromString(controller.message)
            except DecodeError as ex:
                async_result.set_exception(ex)
            else:
                async_result.set(response)
