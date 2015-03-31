__all__ = ['Connection']

import struct
import six
from os import strerror
from io import BytesIO
from collections import deque

from errno import (
    EWOULDBLOCK, ECONNRESET, ENOTCONN, ESHUTDOWN, EISCONN, EALREADY, EINPROGRESS,
    EBADF,
)
from _socket import socket as realsocket, error as socket_error
from _socket import (
    SOL_TCP, SOL_SOCKET, SO_LINGER, TCP_NODELAY, IPPROTO_TCP,
)

from gevent import getcurrent, get_hub, Timeout
from gevent.greenlet import Greenlet
from gevent.core import READ, WRITE, EVENTS

from pymaid.utils import pymaid_logger_wrapper
from pymaid.error import BaseError

range = six.moves.range
hub = get_hub()
main_gr = hub.parent
io, timer = hub.loop.io, hub.loop.timer
del hub

invalid_conn_error = (ECONNRESET, ENOTCONN, ESHUTDOWN, EBADF)
conn_error = (EALREADY, EINPROGRESS, EISCONN, EWOULDBLOCK)


@pymaid_logger_wrapper
class Connection(object):

    CONN_ID = 1
    LINGER_PACK = struct.pack('ii', 1, 0)

    def __init__(self, sock=None, family=2, type_=1, proto=0, server_side=False):
        self._socket = sock = sock or realsocket(family, type_, proto)
        sock.setblocking(0)
        self._setsockopt(sock, server_side)
        self._socket = sock

        self.server_side, self.buf = server_side, BytesIO()
        self.transmission_id, self.transmissions = 1, {}
        self.is_closed, self.close_cb = False, None

        self.conn_id = self.CONN_ID
        Connection.CONN_ID += 1

        self._send_queue = deque()

        self.r_io, self.w_io = io(sock.fileno(), READ), io(sock.fileno(), WRITE)
        self.r_gr, self.fed_write = None, False

    def _setsockopt(self, sock, server_side):
        self.setsockopt = setsockopt = sock.setsockopt
        if sock.family == 2:
            setsockopt(SOL_TCP, TCP_NODELAY, 1)
            setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
        if server_side:
            setsockopt(SOL_SOCKET, SO_LINGER, self.LINGER_PACK)

    def _io_write(self, max_send=5):
        queue = self._send_queue
        qsize = len(queue)
        if not qsize: 
            return

        send = self._socket.send
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
                self.w_io.feed(WRITE, self._io_loop, EVENTS)
                self.fed_write = True
                return
            self.close(ex, reset=True)
        else:
            if qsize > max_send:
                self.w_io.feed(WRITE, self._io_loop, EVENTS)
                self.fed_write = True
            else:
                self.fed_write = False

    def _read(self, size):
        buf = self.buf
        buf.seek(0, 2)
        bufsize = buf.tell()
        self.buf = BytesIO()  # reset self.buf.  we consume it via buf.
        if bufsize >= size:
            buf.seek(0)
            data = buf.read(size)
            self.buf.write(buf.read())
            return data
        recv, r_gr, r_io = self._socket.recv, self.r_gr, self.r_io
        length, remain = 0, size - bufsize
        while 1:
            try:
                data = recv(remain)
            except socket_error as ex:
                if ex.errno == EWOULDBLOCK:
                    r_io.start(r_gr.switch)
                    try:
                        r_gr.parent.switch()
                    except Timeout:
                        self.buf = buf
                        raise
                    finally:
                        r_io.stop()
                    continue
                self.close(ex, reset=True)
                if ex.errno in invalid_conn_error:
                    return buf.getvalue()
                raise
            if not data:
                break
            n = len(data)
            if n == size and not bufsize:
                return data
            buf.write(data)
            del data
            if n == remain:
                break
            remain -= n
        return buf.getvalue()

    def _readline(self, size):
        buf = self.buf
        buf.seek(0, 2)
        bufsize = buf.tell()
        self.buf = BytesIO()
        if bufsize:
            buf.seek(0)
            bline = buf.readline(size)
            if bline.endswith(b'\n') or len(bline) == size:
                self.buf.write(buf.read())
                return bline
            del bline
            buf.seek(0, 2)
        recv, r_gr, r_io = self._socket.recv, self.r_gr, self.r_io
        remain = size - bufsize
        while 1:
            try:
                data = recv(remain)
            except socket_error as ex:
                if ex.errno == EWOULDBLOCK:
                    r_io.start(r_gr.switch)
                    try:
                        r_gr.parent.switch()
                    except Timeout:
                        self.buf = buf
                        raise
                    finally:
                        r_io.stop()
                    continue
                self.close(ex, reset=True)
                if ex.errno in invalid_conn_error:
                    return buf.getvalue()
                raise
            if not data:
                break
            nl = data.find('\n', 0, remain)
            if nl >= 0:
                nl += 1
                self.buf.write(data[nl:])
                if bufsize:
                    buf.write(data[:nl])
                    break
                else:
                    return data[:nl]
            n = len(data)
            if n == size and not bufsize:
                return data
            if n >= remain:
                buf.write(data[:remain])
                self.buf.write(data[remain:])
                break
            buf.write(data)
            remain -= n
        return buf.getvalue()

    def read(self, size, timeout=None):
        assert not self.r_gr, 'read conflict'
        assert getcurrent() != main_gr, 'could not call block func in main loop'
        self.r_gr = getcurrent()
        if not timeout:
            try:
                return self._read(size)
            finally:
                self.r_gr = None
        else:
            assert not self.r_timer, 'duplicated r_timer'
            self.r_timer = timer(timeout)
            self.r_timer.start(self.r_gr.throw, Timeout)
            try:
                return self._read(size)
            finally:
                self.r_timer.stop()
                self.r_gr = self.r_timer = None

    def readline(self, size, timeout=None):
        assert not self.r_gr, 'read conflict'
        assert getcurrent() != main_gr, 'could not call block func in main loop'
        self.r_gr = getcurrent()
        if not timeout:
            try:
                return self._readline(size)
            finally:
                self.r_gr = None
        else:
            assert not self.r_timer, 'duplicated r_timer'
            self.r_timer = timer(timeout)
            self.r_timer.start(self.r_gr.throw, Timeout)
            try:
                return self._readline(size)
            finally:
                self.r_timer.stop()
                self.r_gr = self.r_timer = None

    def write(self, packet_buffer):
        assert packet_buffer
        self._send_queue.append(packet_buffer)
        if not self.fed_write:
            self._io_write()
    send = write

    def connect(self, address, timeout=None):
        assert getcurrent() != main_gr, 'could not call block func in main loop'
        sock = self._socket
        errno = sock.connect_ex(address)
        if errno in conn_error:
            rw_io = io(self.fd, READ | WRITE)
            rw_gr = getcurrent()
            rw_io.start(rw_gr.switch)
            if timeout:
                rw_timer = timer(timeout)
                rw_timer.start(rw_gr.throw, Timeout)
            try:
                rw_gr.parent.switch()
            finally:
                if timeout:
                    rw_timer.stop()
                rw_io.stop()
                rw_timer = rw_io = None
            errno = sock.connect_ex(address)
        if errno != 0 and errno != EISCONN:
            raise socket_error(errno, strerror(errno))

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
            if reset or isinstance(reason, BaseError):
                self.logger.error(
                    '[conn|%d][host|%s][peer|%s] closed with reason: %r',
                    self.conn_id, self.sockname, self.peername, reason
                )
            else:
                self.logger.exception(
                    '[conn|%d][host|%s][peer|%s] closed with reason: %r',
                    self.conn_id, self.sockname, self.peername, reason
                )
        else:
            self.logger.info(
                '[conn|%d][host|%s][peer|%s] closed cleanly',
                self.conn_id, self.sockname, self.peername
            )

        self._send_queue.clear()
        self.w_io.stop()
        self.r_io.stop()
        self._socket.close()
        self.setsockopt = None
        self.buf = BytesIO()

        if self.close_cb:
            self.close_cb(self, reason)
        self.close_cb = None
        self.read = self.readline = lambda *args, **kwargs: ''
        self.write = self.send = lambda *args, **kwargs: ''

    @property
    def peername(self):
        return self._socket.getpeername()

    @property
    def sockname(self):
        return self._socket.getsockname()

    @property
    def fd(self):
        return self._socket.fileno()
