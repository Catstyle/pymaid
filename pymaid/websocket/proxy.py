__all__ = ['WebSocketProxy']

import struct

from errno import EINVAL, ENOTCONN, EWOULDBLOCK
from _socket import error as socket_error
from collections import deque

from gevent.greenlet import Greenlet
from gevent.core import WRITE
from geventwebsocket.websocket import Header

from pymaid.utils import pymaid_logger_wrapper, io
from pymaid.error.base import BaseEx


@pymaid_logger_wrapper
class WebSocketProxy(object):

    CONN_ID = 1
    LINGER_PACK = struct.pack('ii', 1, 0)

    def __init__(self, channel, ws):
        self.channel = channel
        self.ws = ws
        self._socket = ws.handler.socket
        self.transmission_id, self.transmissions = 1, {}
        self.is_closed, self.close_cb = False, None
        self.server_side = False

        self.conn_id = self.CONN_ID
        WebSocketProxy.CONN_ID += 1

        self._send_queue = deque()
        self.w_io = io(self._socket.fileno(), WRITE)
        self.r_gr, self.fed_write = None, False

    def _io_write(self, max_send=5):
        queue = self._send_queue
        send, qsize = self._socket.send, len(queue)
        assert qsize, qsize

        self._socket.setblocking(0)
        try:
            for _ in range(min(qsize, max_send)):
                buf = queue[0]
                # see pydoc of socket.send
                sent, bufsize = 0, len(buf)
                membuf = memoryview(buf)
                sent += send(membuf)
                while sent < bufsize:
                    sent += send(membuf[sent:])
                queue.popleft()
        except socket_error as ex:
            if ex.errno == EWOULDBLOCK:
                queue[0] = membuf[sent:]
                self.w_io.feed(WRITE, self._io_write)
                self.fed_write = True
                return
            self.close(ex, reset=True)
        else:
            if qsize > max_send:
                self.w_io.feed(WRITE, self._io_write)
                self.fed_write = True
            else:
                self.fed_write = False
        self._socket.setblocking(1)

    @property
    def peername(self):
        try:
            return self._socket.getpeername()
        except socket_error as err:
            if err.errno == EINVAL:
                return 'invalid in shutdown socket on osx'
            elif err.errno == ENOTCONN:
                return 'ENOTCONN'
            raise

    @property
    def sockname(self):
        return self._socket.getsockname()

    @property
    def fd(self):
        return self._socket.fileno()

    def write(self, packet_buffer):
        assert packet_buffer
        header = Header.encode_header(
            True, self.ws.OPCODE_BINARY, '', len(packet_buffer), 0
        )
        self._send_queue.append(header + packet_buffer)
        if not self.fed_write:
            self._io_write()
    send = write

    def set_close_cb(self, close_cb):
        assert not self.close_cb
        assert callable(close_cb)
        self.close_cb = close_cb

    def close(self, reason=None, reset=False):
        if self.is_closed:
            return
        self.is_closed = True

        if isinstance(reason, Greenlet):
            reason = reason.exception

        if reason:
            if reset or isinstance(reason, BaseEx):
                log = self.logger.error
            else:
                log = self.logger.exception
        else:
            log = self.logger.info
        log('[conn|%d][host|%s][peer|%s] closed with reason: %r',
            self.conn_id, self.sockname, self.peername, reason)

        self.ws.close()
        self._send_queue.clear()
        self.w_io.stop()

        if self.close_cb:
            self.close_cb(self, reason)
        self.close_cb = None

    def __getattr__(self, name):
        return getattr(self.ws, name)
