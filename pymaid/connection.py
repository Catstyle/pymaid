from io import BytesIO
from weakref import WeakValueDictionary

import errno
import socket
from socket import error as socket_error
from socket import AF_INET, AF_UNIX

from six import string_types

from greenlet import getcurrent, greenlet as Greenlet

from .conf import settings
from .core import timer, io, hub
from .error import RpcError
from .utils.logger import pymaid_logger_wrapper

__all__ = ['Connection']


def set_socket_default_options(sock):
    if sock.family == socket.AF_INET:
        setsockopt = sock.setsockopt
        getsockopt = sock.getsockopt
        SOL_SOCKET, SOL_TCP = socket.SOL_SOCKET, socket.SOL_TCP

        setsockopt(SOL_TCP, socket.TCP_NODELAY, 1)
        setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        ns = settings.namespaces['pymaid']  # should always exists
        if getsockopt(SOL_SOCKET, socket.SO_SNDBUF) < ns['SO_SNDBUF']:
            setsockopt(SOL_SOCKET, socket.SO_SNDBUF, ns['SO_SNDBUF'])
        if getsockopt(SOL_SOCKET, socket.SO_RCVBUF) < ns['SO_RCVBUF']:
            setsockopt(SOL_SOCKET, socket.SO_RCVBUF, ns['SO_RCVBUF'])

        if ns['PM_KEEPALIVE']:
            setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            setsockopt(SOL_TCP, socket.TCP_KEEPIDLE, ns['PM_KEEPIDLE'])
            setsockopt(
                SOL_TCP, socket.TCP_KEEPINTVL, ns['PM_KEEPINTVL']
            )
            setsockopt(SOL_TCP, socket.TCP_KEEPCNT, ns['PM_KEEPCNT'])


@pymaid_logger_wrapper
class Connection(object):

    CONNID = 1

    def __init__(self, sock, client_side=False):
        self._socket = sock
        sock.setblocking(0)
        self.client_side = client_side
        self.chunk_size = max(
            sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF),
            1024 * 1024
        )

        self.buf = BytesIO()
        self.transmission_id, self.transmissions = 1, WeakValueDictionary()
        self.is_closed, self.close_callbacks = False, []
        self.is_connected = True

        set_socket_default_options(sock)

        self.connid = Connection.CONNID
        Connection.CONNID += 1
        self.peername = sock.getpeername()
        self.sockname = sock.getsockname()
        fd = self.fd = sock.fileno()

        self._send_queue = []
        # 1: READ, 2: WRITE
        self.r_io, self.w_io = io(fd, 1), io(fd, 2)
        self.r_timer = None

    def _send(self):
        '''try to send all packets to reduce system call'''
        if not self._send_queue:
            self.w_io.stop()
            return

        membuf = memoryview(b''.join(self._send_queue))
        del self._send_queue[:]
        len_of_membuf = len(membuf)
        sent = 0
        chunk_size = self.chunk_size
        try:
            while sent < len_of_membuf:
                # see pydoc of socket.send
                sent += self._socket.send(membuf[sent:sent + chunk_size])
        except socket_error as ex:
            if sent < len_of_membuf:
                self._send_queue.append(membuf[sent:].tobytes())
            if ex.errno == errno.EWOULDBLOCK:
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
        recvsize = settings.namespaces['pymaid']['MAX_RECV_SIZE']
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
        recvsize = settings.namespaces['pymaid']['MAX_RECV_SIZE']
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
            nl = data.find(b'\n', 0, remain)
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
        sock = socket.socket(
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
            async_result.set_exception(ex)
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
