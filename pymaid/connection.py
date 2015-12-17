__all__ = ['Connection']

import struct
from os import strerror
from io import BytesIO
from collections import deque

from errno import (
    EWOULDBLOCK, ECONNRESET, ENOTCONN, ESHUTDOWN, EISCONN, EALREADY,
    EINPROGRESS, EBADF
)
from _socket import socket as realsocket, error as socket_error
from _socket import (
    SOL_TCP, SOL_SOCKET, SO_LINGER, TCP_NODELAY, IPPROTO_TCP,
)
from _socket import AF_INET, SOCK_STREAM

from gevent import getcurrent, Timeout
from gevent.greenlet import Greenlet
from gevent.core import READ, WRITE

from pymaid.error import RpcError
from pymaid.utils import timer, io, hub

invalid_conn = (ECONNRESET, ENOTCONN, ESHUTDOWN, EBADF)
connecting_error = (EALREADY, EINPROGRESS, EISCONN, EWOULDBLOCK)


class Connection(object):

    CONNID = 1
    LINGER_PACK = struct.pack('ii', 1, 0)

    def __init__(self, sock):
        self._socket = sock
        sock.setblocking(0)
        self._setsockopt(sock)
        self._socket = sock

        self.buf = BytesIO()
        self.transmission_id, self.transmissions = 1, {}
        self.is_closed, self.close_cb = False, None

        self.connid = Connection.CONNID
        Connection.CONNID += 1
        self.peername = sock.getpeername()
        self.sockname = sock.getsockname()
        fd = self.fd = sock.fileno()

        self._send_queue = deque()
        self.r_io, self.w_io = io(fd, READ), io(fd, WRITE)
        self.r_gr, self.fed_write = None, False

    def __del__(self):
        try:
            self.close()
        except:
            # close() may fail if __init__ didn't complete
            pass

    def _setsockopt(self, sock):
        setsockopt = sock.setsockopt
        if sock.family == AF_INET:
            setsockopt(SOL_TCP, TCP_NODELAY, 1)
            setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
        setsockopt(SOL_SOCKET, SO_LINGER, self.LINGER_PACK)

    def _send(self, max_send=5):
        qsize = len(self._send_queue)
        if qsize == 0:
            return

        send, queue = self._socket.send, self._send_queue
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
                self.w_io.feed(WRITE, self._send)
                self.fed_write = True
                return
            if not self.is_closed:
                self.close(ex, reset=True)
        else:
            if qsize > max_send:
                self.w_io.feed(WRITE, self._send)
                self.fed_write = True
            else:
                self.fed_write = False

    def _sendall(self):
        """ block current greenlet util all data sent"""
        w_gr, w_io = getcurrent(), self.w_io
        assert w_gr != hub, 'could not call block func in main loop'
        queue = self._send_queue
        while 1:
            self._send(len(queue))
            if len(queue) == 0 or self.is_closed:
                break
            w_io.start(w_gr.switch)
            try:
                w_gr.parent.switch()
            finally:
                w_io.stop()

    def _read(self, size):
        buf = self.buf
        buf.seek(0, 2)
        bufsize = buf.tell()
        if bufsize >= size:
            buf.seek(0)
            data = buf.read(size)
            self.buf = BytesIO()
            self.buf.write(buf.read())
            return data
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
                if ex.errno in invalid_conn:
                    return buf.getvalue()
                raise
            if not data:
                break
            n = len(data)
            if n == size:
                return data
            buf.write(data)
            del data
            if n == remain:
                break
            remain -= n
        self.buf = BytesIO()
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
                if ex.errno in invalid_conn:
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
            if n == size:
                return data
            buf.write(data)
            if n == remain:
                break
            remain -= n
        return buf.getvalue()

    @classmethod
    def connect(cls, address, timeout=None, family=AF_INET,
                type_=SOCK_STREAM, proto=0):
        assert getcurrent() != hub, 'could not call block func in main loop'
        sock = realsocket(family, type_, proto)
        errno = sock.connect_ex(address)
        if errno in connecting_error:
            rw_io = io(sock.fileno(), READ | WRITE)
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
        return cls(sock)

    def read(self, size, timeout=None):
        assert not self.r_gr, 'read conflict'
        assert getcurrent() != hub, 'could not call block func in main loop'
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
        assert getcurrent() != hub, 'could not call block func in main loop'
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

    def send(self, packet_buffer):
        self._send_queue.append(packet_buffer)
        if not self.fed_write:
            self._send()
    write = send

    def oninit(self):
        """
        Called by handler once handler start on a greenlet.

        return True to continue or False to terminate.
        """
        return True

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

        ex = reason or RpcError.EOF()
        for async_result in self.transmissions.values():
            # we should not reach here with async_result left
            # that should be an exception
            async_result.set_exception(ex)
        self.transmissions.clear()

        self._send_queue.clear()
        self.w_io.stop()
        self.r_io.stop()
        if self.r_gr:
            self.r_gr.kill(block=False)
        self.buf = BytesIO()

        if self.close_cb:
            self.close_cb(self, reason, reset)
        self.close_cb = None
        self._socket.close()

    def delay_close(self, reason=None, reset=False):
        if self.is_closed:
            return
        self.read = self.readline = lambda *args, **kwargs: ''
        self.write = self.send = lambda *args, **kwargs: ''
        # _sendall will check is_closed to avoid recursion
        self.is_closed = True
        self._sendall()
        # super close need is_closed = False
        self.is_closed = False
        self.close(reason, reset)
