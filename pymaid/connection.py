__all__ = ['Connection']

import time
import struct

from gevent.hub import get_hub
from gevent.greenlet import Greenlet
from gevent.queue import Queue
from gevent import socket
from gevent.core import READ, WRITE

from pymaid.agent import ServiceAgent
from pymaid.apps.monitor import MonitorService_Stub
from pymaid.utils import greenlet_pool, logger_wrapper
from pymaid.error import HeartbeatTimeout


@logger_wrapper
class Connection(object):

    HEADER = '!I'
    HEADER_LENGTH = struct.calcsize(HEADER)

    # see /proc/sys/net/core/rmem_default and /proc/sys/net/core/rmem_max
    # the doubled value is max size for one socket recv call
    # you need to ensure *MAX_RECV* times *MAX_PACKET_LENGTH* is lower the that
    # in some situation, the basic value is something like 212992
    # so MAX_RECV * MAX_PACKET_LENGTH = 81920 < 212992 is ok here
    MAX_SEND = 10
    MAX_RECV = 10
    MAX_PACKET_LENGTH = 8 * 1024
    RCVBUF = MAX_RECV * MAX_PACKET_LENGTH
    MAX_IDLE_LOOP = 2

    LINGER_PACK = struct.pack('ii', 1, 0)
    CONN_ID = 1

    __slots__ = [
        'hub', 'server_side', 'peername', 'sockname', 'is_closed', 'conn_id',
        'buffers', 'gr', 'fileno',  'last_check_heartbeat', 'transmissions',
        'need_heartbeat', 'heartbeat_interval',
        '_heartbeat_timeout_counter', '_max_heartbeat_timeout_count',
        '_idle_loop', '_socket', '_send_queue', '_recv_queue', '_socket_watcher',
        '_close_cb', '_monitor_agent', '_has_spawn_send'
    ]

    def __init__(self, sock, server_side):
        self.hub = get_hub()
        self.server_side = server_side

        self._setsockopt(sock)
        self._socket = sock
        self.peername = sock.getpeername()
        self.sockname = sock.getsockname()

        self.is_closed = False
        self._close_cb = None
        self._idle_loop = 0
        self._monitor_agent = None
        self._has_spawn_send = 0
        self.need_heartbeat = 0

        self.conn_id = self.__class__.CONN_ID
        self.__class__.CONN_ID += 1
        self.fileno = sock.fileno()

        self.buffers = []
        self.transmissions = set()
        self._send_queue = Queue()
        self._recv_queue = Queue()

        self._socket_watcher = self.hub.loop.io(self.fileno, READ)
        self._socket_watcher.start(self._recv_loop)

    def _setsockopt(self, sock):
        sock.setblocking(0)
        sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, self.LINGER_PACK)
        # system will doubled this buffer
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.RCVBUF/2)

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

    def clear_heartbeat_counter(self):
        self.last_check_heartbeat = time.time()
        self._heartbeat_timeout_counter = 0

    def heartbeat_timeout(self):
        self._heartbeat_timeout_counter += 1
        if self._heartbeat_timeout_counter >= self._max_heartbeat_timeout_count:
            self.close(HeartbeatTimeout(host=self.sockname, peer=self.peername))

    def notify_heartbeat(self):
        self._monitor_agent.notify_heartbeat()

    def send(self, packet_buffer):
        assert packet_buffer
        self._send_queue.put(packet_buffer)
        if not self._has_spawn_send:
            greenlet_pool.spawn(self._send_loop)
            self._has_spawn_send = 1
        #self._idle_loop = 0
        #if not self._socket_watcher.events & WRITE:
        #    self._socket_watcher.feed(WRITE, self._io_loop, EVENTS)

    def recv(self, timeout=None):
        return self._recv_queue.get(timeout=timeout)

    def close(self, reason=None, reset=False):
        if self.is_closed:
            return
        self.is_closed = True
        #print 'connection close', reason, self.sockname, self.peername

        if isinstance(reason, Greenlet):
            reason = reason.exception
        self.logger.info(
            '[host|%s][peer|%s] closed with reason: %s',
            self.sockname, self.peername, reason
        )

        if self._monitor_agent is not None:
            self._monitor_agent.close()

        #if reason is None and not reset:
        #    self._socket.sendall('')
        self._send_queue.queue.clear()
        self._recv_queue.queue.clear()
        self._socket_watcher.stop()
        self._socket.close()
        del self.buffers[:]

        if self._close_cb:
            self._close_cb(self, reason)

    def set_close_cb(self, close_cb):
        assert self._close_cb is None
        assert callable(close_cb)
        self._close_cb = close_cb
    
    def _io_loop(self, event):
        #print '_io_loop', event, self.conn_id
        if event & READ:
            self._recv_loop()
        if event & WRITE:
            self._send_loop()

    def _send_loop(self):
        qsize = self._send_queue.qsize()
        #if qsize == 0:
        #    self._idle_loop += 1
        #    if self._idle_loop >= self.MAX_IDLE_LOOP:
        #        self._socket_watcher.stop()
        #        self._socket_watcher = self.hub.loop.io(self.fileno, READ)
        #        self._socket_watcher.start(self._io_loop, pass_events=True)
        #    return

        get_packet, sendall = self._send_queue.get_nowait, self._socket.sendall
        pack, HEADER, MAX_SEND = struct.pack, self.HEADER, self.MAX_SEND
        try:
            for _ in xrange(min(qsize, MAX_SEND)):
                packet_buffer = get_packet()
                if packet_buffer is None:
                    break

                header_buffer = pack(HEADER, len(packet_buffer))
                # see pydoc of socket.sendall
                #print 'send_loop', header_buffer+packet_buffer
                sendall(header_buffer+packet_buffer)
        except socket.error as ex:
            self.close(ex)
        if qsize > MAX_SEND:
            greenlet_pool.spawn(self._send_loop)
        else:
            self._has_spawn_send = 0

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

    def _recv_loop(self):
        length = self._recv_n(self.RCVBUF)

        # handle all received data even if receive EOF or catch exception
        buffers, recv_packet = ''.join(self.buffers), self._recv_queue.put
        count, buffers_length, unpack = 0, len(buffers), struct.unpack
        HEADER, HEADER_LENGTH = self.HEADER, self.HEADER_LENGTH
        MAX_PACKET_LENGTH = self.MAX_PACKET_LENGTH
        while count < buffers_length:
            header = buffers[count:count+HEADER_LENGTH]
            if len(header) < HEADER_LENGTH:
                break
            count += HEADER_LENGTH

            packet_length = unpack(HEADER, header)[0]
            if packet_length >= MAX_PACKET_LENGTH:
                self.close('[packet_length|%d] out of limitation' % packet_length)
                break

            packet_buffer = buffers[count:count+packet_length]
            if len(packet_buffer) < packet_length:
                break
            #print 'recv_packet', packet_buffer
            recv_packet(packet_buffer)
            count += packet_length

        del self.buffers[:]
        if count < buffers_length and not self.is_closed:
            self.buffers.append(buffers[count:])

        # close if receive EOF or catch exception
        if length == 0:
            self.close('has received EOF', reset=True)
        elif not isinstance(length, (int, long)):
            # exception
            self.close(length, reset=True)
