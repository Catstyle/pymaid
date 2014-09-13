import struct
from gevent.hub import get_hub
from gevent.greenlet import Greenlet
from gevent.queue import Queue
from gevent import socket
from google.protobuf.message import DecodeError

from pymaid.controller import Controller
from pymaid.agent import ServiceAgent
from pymaid.apps.monitor import MonitorService_Stub
from pymaid.utils import greenlet_pool, logger_wrapper
from pymaid.error import HeartbeatTimeout

__all__ = ['Connection']


@logger_wrapper
class Connection(object):

    HEADER = '!I'
    HEADER_LENGTH = struct.calcsize(HEADER)
    MAX_PACKET_LENGTH = 10 * 1024

    LINGER_PACK = struct.pack('ii', 1, 0)
    CONN_ID = 1000000

    def __init__(self, sock, server_side):
        self.setsockopt(sock)
        self._peer_name = sock.getpeername()
        self._sock_name = sock.getsockname()
        self._socket = sock
        self._server_side = server_side

        self._is_closed = False
        self._conn_id = self.__class__.CONN_ID
        self.__class__.CONN_ID += 1
        if self.__class__.CONN_ID >= 2 ** 32:
            self.__class__.CONN_ID = 1000000
        self._close_cb = None

        self._send_queue = Queue()
        self._recv_queue = Queue()

        self._send_let = greenlet_pool.spawn(self._send_loop)
        self._send_let.link(self.close)

        self._recv_let = greenlet_pool.spawn(self._recv_loop)
        self._recv_let.link(self.close)

    def setsockopt(self, sock):
        sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, self.LINGER_PACK)

    def setup_server_heartbeat(self, interval, max_timeout_count):
        assert interval > 0
        assert max_timeout_count >= 1

        self._heartbeat_interval = interval
        self._heartbeat_timeout_counter = 0
        self._max_heartbeat_timeout_count = max_timeout_count
        self._heartbeat_timeout_cb = self._heartbeat_timeout
        self._start_heartbeat_timer()

    def setup_client_heartbeat(self, channel):
        self._monitor_agent = ServiceAgent(MonitorService_Stub(channel))
        resp = self._monitor_agent.get_heartbeat_info(conn=self)

        if not resp.need_heartbeat:
            return
        self._heartbeat_interval = resp.heartbeat_interval
        self._heartbeat_timeout_cb = self._send_heartbeat
        self._start_heartbeat_timer()

    def clear_heartbeat_counter(self):
        self._heartbeat_timeout_counter = 0
        self._start_heartbeat_timer()

    def _start_heartbeat_timer(self):
        if self._heartbeat_timer is not None:
            self._heartbeat_timer.stop()
        self._heartbeat_timer = get_hub().loop.timer(self._heartbeat_interval)
        self._heartbeat_timer.start(self._heartbeat_timeout_cb)

    def _heartbeat_timeout(self):
        self._heartbeat_timeout_counter += 1
        if self._heartbeat_timeout_counter >= self._max_heartbeat_timeout_count:
            self.close(HeartbeatTimeout(host=self.sockname, peer=self.peername))
        else:
            self._start_heartbeat_timer()

    def _send_heartbeat(self):
        # TODO: add send heartbeat
        self._monitor_agent.notify_heartbeat()
        self._start_heartbeat_timer()

    def send(self, packet_buff):
        assert packet_buff
        self._send_queue.put(packet_buff)

    def recv(self, timeout=None):
        return self._recv_queue.get(timeout=timeout)

    def unlink_close(self):
        self._recv_let.unlink(self.close)
        self._send_let.unlink(self.close)

    def close(self, reason=None):
        #print 'connection close', why
        if self._is_closed:
            return
        self._is_closed = True

        self.unlink_close()
        if reason is not None and isinstance(reason, Greenlet):
            reason = reason.exception

        if reason is not None:
            self.logger.error(
                '[host|%s][peer|%s] closed with reason: %s',
                self.sockname, self.peername, reason
            )

        self._socket.close()
        if not self._send_let.dead:
            self._send_queue.put(None)
            self._send_let.kill(block=False)

        if not self._recv_let.dead:
            self._recv_queue.queue.clear()
            self._recv_queue.put(None)
            self._recv_let.kill(block=False)

        if self._close_cb:
            self._close_cb(self, reason)

    def set_close_cb(self, close_cb):
        assert self._close_cb is None
        assert callable(close_cb)
        self._close_cb = close_cb

    @property
    def sockname(self):
        return self._sock_name

    @property
    def peername(self):
        return self._peer_name

    @property
    def is_closed(self):
        return self._is_closed

    @property
    def conn_id(self):
        return self._conn_id

    def _send_loop(self):
        get_packet, sendall = self._send_queue.get, self._socket.sendall
        pack = struct.pack
        while 1:
            controller = get_packet()
            if controller is None:
                break

            controller_buffer = controller.meta_data.SerializeToString()
            header_buffer = pack(self.HEADER, len(controller_buffer))
            try:
                # see pydoc of socket.sendall
                result = sendall(header_buffer+controller_buffer)
            except socket.error as ex:
                self.logger.error(
                    '[host|%s][peer|%s] send with exception: %s',
                    self.sockname, self.peername, ex
                )
                break
            if result is not None:
                break

    def _recv_n(self, nbytes):
        recv, buff = self._socket.recv, ''
        while len(buff) < nbytes:
            try:
                t = recv(nbytes - len(buff))
                if not t:
                    self.logger.debug(
                        '[host|%s][peer|%s] has received EOF',
                        self.sockname, self.peername
                    )
                    return
                buff += t
            except socket.error as ex:
                self.logger.error(
                    '[host|%s][peer|%s] recv with exception: %s',
                    self.sockname, self.peername, ex
                )
                break
        return buff

    def _recv_loop(self):
        recv_n, unpack = self._recv_n, struct.unpack
        recv_package = self._recv_queue.put
        HEADER, MAX_PACKET_LENGTH = self.HEADER, self.MAX_PACKET_LENGTH
        while 1:
            header = recv_n(self.HEADER_LENGTH)
            if not header:
                break

            controller_length, = unpack(HEADER, header)
            if controller_length >= MAX_PACKET_LENGTH:
                self.logger.error(
                    '[host|%s][peer|%s] closed with invalid payload [length|%d]',
                    self.sockname, self.peername, controller_length
                )
                return

            controller_buffer = recv_n(controller_length)
            controller = Controller()
            controller.conn = self
            try:
                controller.meta_data.ParseFromString(controller_buffer)
            except DecodeError as ex:
                self.logger.exception('process packet with decode error', ex)
                break

            recv_package(controller)
