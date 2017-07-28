from io import BytesIO

import errno
import socket
from socket import error as socket_error
from socket import AF_INET, AF_UNIX

from six import string_types

from gevent import getcurrent
from gevent.greenlet import Greenlet
from gevent.socket import socket as realsocket

from pymaid.conf import settings
from pymaid.error import RpcError
from pymaid.utils import timer, io, hub
from pymaid.utils.logger import pymaid_logger_wrapper

__all__ = ['Connection']


@pymaid_logger_wrapper
class Connection(object):

    CONNID = 1

    def __init__(self, sock, client_side=False):
        self._socket = sock
        sock.setblocking(0)
        self._setsockopt(sock)
        self.client_side = client_side

        self.buf = BytesIO()
        self.transmission_id, self.transmissions = 1, {}
        self.is_closed, self.close_callbacks = False, []
        self.is_connected = True

        self.connid = Connection.CONNID
        Connection.CONNID += 1
        self.peername = sock.getpeername()
        self.sockname = sock.getsockname()
        fd = self.fd = sock.fileno()

        self._send_queue = []
        # 1: READ, 2: WRITE
        self.r_io, self.w_io = io(fd, 1), io(fd, 2)
        self.w_retry = 0
        self.r_timer = None

    def _setsockopt(self, sock):
        setsockopt = sock.setsockopt
        if sock.family == socket.AF_INET:
            SOL_TCP = socket.SOL_TCP
            setsockopt(SOL_TCP, socket.TCP_NODELAY, 1)
            setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            if settings.PM_KEEPALIVE:
                setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                setsockopt(SOL_TCP, socket.TCP_KEEPIDLE, settings.PM_KEEPIDLE)
                setsockopt(
                    SOL_TCP, socket.TCP_KEEPINTVL, settings.PM_KEEPINTVL
                )
                setsockopt(SOL_TCP, socket.TCP_KEEPCNT, settings.PM_KEEPCNT)

    def _send(self):
        '''try to send all packets to reduce system call'''
        if not self._send_queue:
            self.w_retry = 0
            self.w_io.stop()
            return

        membuf = memoryview(''.join(self._send_queue))
        try:
            # see pydoc of socket.send
            sent = self._socket.send(membuf)
            del self._send_queue[:]
            if sent < len(membuf):
                self._send_queue.append(membuf[sent:].tobytes())
                self.w_io.start(self._send)
            else:
                self.w_retry = 0
                self.w_io.stop()
        except socket_error as ex:
            if ex.errno == errno.EWOULDBLOCK:
                self.w_retry += 1
                if self.w_retry > settings.WRETRY:
                    self.close('max retried: %d' % self.w_retry, reset=True)
                else:
                    self.w_io.start(self._send)
            else:
                self.close(ex, reset=True)

    def _sendall(self):
        """ block current greenlet util all data sent"""
        w_gr, w_io = getcurrent(), self.w_io
        assert w_gr != hub, 'could not call block func in main loop'
        queue = self._send_queue
        while 1:
            self._send()
            if not queue:
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
        self.buf = BytesIO()
        if bufsize >= size:
            buf.seek(0)
            data = buf.read(size)
            self.buf.write(buf.read())
            return data

        recv = self._socket.recv
        recvsize = settings.MAX_RECV_SIZE
        while 1:
            try:
                data = recv(recvsize)
            except socket_error as ex:
                if ex.errno == errno.EWOULDBLOCK:
                    gr = getcurrent()
                    self.r_io.start(gr.switch)
                    try:
                        gr.parent.switch()
                    except RpcError.Timeout:
                        self.buf = buf
                        raise
                    finally:
                        self.r_io.stop()
                    continue
                self.close(ex, reset=True)
                # 9: EBADF, 104: ECONNRESET
                if ex.errno in {9, 104}:
                    return buf.getvalue()
                raise
            if not data:
                break
            n = len(data)
            if n == size and not bufsize:
                return data
            remain = size - bufsize
            if n >= remain:
                buf.write(data[:remain])
                self.buf.write(data[remain:])
                break
            buf.write(data)
            del data
            bufsize += n
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

        recv = self._socket.recv
        recvsize = settings.MAX_RECV_SIZE
        while 1:
            try:
                data = recv(recvsize)
            except socket_error as ex:
                if ex.errno == errno.EWOULDBLOCK:
                    gr = getcurrent()
                    self.r_io.start(gr.switch)
                    try:
                        gr.parent.switch()
                    except RpcError.Timeout:
                        self.buf = buf
                        raise
                    finally:
                        self.r_io.stop()
                    continue
                self.close(ex, reset=True)
                # 9: EBADF, 104: ECONNRESET
                if ex.errno in {9, 104}:
                    return buf.getvalue()
                raise
            if not data:
                break
            remain = size - bufsize
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
            del data
            bufsize += n
        return buf.getvalue()

    @classmethod
    def connect(cls, address, client_side=True, timeout=None,
                type_=socket.SOCK_STREAM):
        assert getcurrent() != hub, 'could not call block func in main loop'
        sock = realsocket(
            AF_UNIX if isinstance(address, string_types) else AF_INET, type_
        )
        sock.connect(address)
        return cls(sock, client_side)

    def read(self, size, timeout=None):
        assert getcurrent() != hub, 'could not call block func in main loop'
        if not timeout:
            return self._read(size)
        else:
            assert not self.r_timer, 'duplicated r_timer'
            self.r_timer = timer(timeout)
            self.r_timer.start(getcurrent().throw, RpcError.Timeout(timeout))
            try:
                return self._read(size)
            finally:
                self.r_timer.stop()
                self.r_timer = None

    def readline(self, size, timeout=None):
        assert getcurrent() != hub, 'could not call block func in main loop'
        if not timeout:
            return self._readline(size)
        else:
            assert not self.r_timer, 'duplicated r_timer'
            self.r_timer = timer(timeout)
            self.r_timer.start(getcurrent().throw, RpcError.Timeout(timeout))
            try:
                return self._readline(size)
            finally:
                self.r_timer.stop()
                self.r_timer = None

    def send(self, data):
        self._send_queue.append(data)
        self._send()
    write = send

    def oninit(self):
        '''Called by handler once handler start on a greenlet.

        return True to continue or False to terminate.
        '''
        return True

    def add_close_cb(self, close_cb):
        '''last added close callback will be called first'''
        assert close_cb not in self.close_callbacks
        assert callable(close_cb)
        self.close_callbacks.append(close_cb)

    def close(self, reason=None, reset=False):
        del self._send_queue[:]
        self.w_io.stop()
        self.r_io.stop()
        self.buf = BytesIO()
        self._socket.close()

        if self.r_timer:
            self.r_timer.stop()

        self.is_closed = True

        if isinstance(reason, Greenlet):
            reason = reason.exception

        ex = reason or RpcError.EOF()
        for async_result in self.transmissions.values():
            # we should not reach here with async_result left
            # that should be an exception
            async_result[0].set_exception(ex)
        self.transmissions.clear()

        callbacks = self.close_callbacks[::-1]
        del self.close_callbacks[:]
        for cb in callbacks:
            cb(self, reason, reset)

    def delay_close(self, reason=None, reset=False):
        self.read = self.readline = lambda *args, **kwargs: ''
        self.write = self.send = lambda *args, **kwargs: None
        self._sendall()
        self.close(reason, reset)

    def __str__(self):
        return u'[conn|%d][host|%s][peer|%s][is_closed|%s]' % (
            self.connid, self.sockname, self.peername, self.is_closed
        )
    __unicode__ = __repr__ = __str__


class DisconnectedConnection(Connection):

    def __init__(self):
        self.connid = 0
        self.transmission_id = 0
        self.sockname = self.peername = 'disconnected'
        self.is_closed = True

    def send(self, data):
        pass
    write = send

    def read(self, size, timeout=None):
        pass
    readline = read

    def close(self, reason=None, reset=False):
        pass
