import os
import errno
import socket
from socket import error as socket_error

from six import string_types
from gevent.socket import socket as realsocket

from pymaid.connection import Connection
from pymaid.conf import settings
from pymaid.error.base import BaseEx
from pymaid.utils import greenlet_pool, io
from pymaid.utils.logger import pymaid_logger_wrapper

__all__ = ['ServerChannel', 'ClientChannel']


@pymaid_logger_wrapper
class BaseChannel(object):

    def __init__(self, handler, connection_class=Connection):
        self.handler = handler
        self.connection_class = connection_class
        self.connections = {}

    def _connection_attached(self, conn):
        self.logger.info(
            '[conn|%d][host|%s][peer|%s] made',
            conn.connid, conn.sockname, conn.peername
        )
        assert conn.connid not in self.connections
        self.connections[conn.connid] = conn
        conn.add_close_cb(self._connection_detached)
        conn.worker_gr = greenlet_pool.spawn(self.handler, conn)
        conn.worker_gr.link_exception(conn.close)
        self.connection_attached(conn)

    def _connection_detached(self, conn, reason=None, reset=False):
        log = self.logger.info
        if reason:
            if isinstance(reason, (BaseEx, string_types, int)):
                log = self.logger.error
            else:
                log = self.logger.exception
        log('[conn|%d][host|%s][peer|%s] closed with reason: %r',
            conn.connid, conn.sockname, conn.peername, reason)
        conn.worker_gr.kill(block=False)
        assert conn.connid in self.connections
        del self.connections[conn.connid]
        self.connection_detached(conn, reason)

    @property
    def is_full(self):
        return len(self.connections) >= settings.MAX_CONCURRENCY

    def connection_attached(self, conn):
        pass

    def connection_detached(self, conn, reason=None):
        pass

    def stop(self, reason='Channel calls stop'):
        for conn in self.connections.values()[:]:
            conn.delay_close(reason)
        self.connections.clear()


@pymaid_logger_wrapper
class ServerChannel(BaseChannel):

    def __init__(self, handler, connection_class=Connection):
        super(ServerChannel, self).__init__(handler, connection_class)
        self.accept_watchers = []
        self.middlewares = []
        self.is_paused = False

    def _do_accept(self, sock):
        accept, attach_connection = sock.accept, self._connection_attached
        ConnectionClass = self.connection_class
        cnt = err = 0
        while 1:
            if cnt >= settings.MAX_ACCEPT:
                break
            if self.is_full:
                self.pause()
                break
            try:
                peer_socket, address = accept()
                attach_connection(ConnectionClass(peer_socket))
            except socket_error as ex:
                if ex.errno == errno.EWOULDBLOCK:
                    break
                peer_socket.close()
                if ex.errno in {errno.ECONNABORTED, errno.ENOTCONN}:
                    err += 1
                    continue
                self.logger.exception(ex)
                break
            except Exception as ex:
                peer_socket.close()
                self.logger.exception(ex)
                break
            cnt += 1

    def _connection_attached(self, conn):
        super(ServerChannel, self)._connection_attached(conn)
        for middleware in self.middlewares:
            middleware.on_connect(conn)

    def _connection_detached(self, conn, reason=None, reset=False):
        super(ServerChannel, self)._connection_detached(conn, reason, reset)
        for middleware in self.middlewares:
            middleware.on_close(conn)
        if self.is_paused and not self.is_full:
            self.start()

    def listen(self, address, backlog=256, type_=socket.SOCK_STREAM):
        # not support ipv6 yet
        if isinstance(address, string_types):
            family = socket.AF_UNIX
            if os.path.exists(address):
                os.unlink(address)
        else:
            family = socket.AF_INET
        self.logger.info(
            '[listening|%s][type|%s][backlog|%d]', address, type_, backlog
        )
        sock = realsocket(family, type_)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # should explicitly set SO_REUSEPORT
        # sock.setsockopt(SOL_SOCKET, SO_REUSEPORT, 1)
        sock.bind(address)
        sock.listen(backlog)
        sock.setblocking(0)
        self.accept_watchers.append((io(sock.fileno(), 1), sock))

    def append_middleware(self, middleware):
        self.middlewares.append(middleware)

    def start(self):
        self.is_paused = False
        for watcher, sock in self.accept_watchers:
            if not watcher.active:
                watcher.start(self._do_accept, sock)

    def pause(self):
        self.is_paused = True
        for watcher, sock in self.accept_watchers:
            if watcher.active:
                watcher.stop()

    def stop(self, reason='ServerChannel calls stop'):
        self.pause()
        super(ServerChannel, self).stop(reason)


@pymaid_logger_wrapper
class ClientChannel(BaseChannel):

    def __init__(self, handler=lambda conn: '', connection_class=Connection):
        super(ClientChannel, self).__init__(handler, connection_class)

    def connect(self, address, type_=socket.SOCK_STREAM, timeout=None):
        conn = self.connection_class.connect(address, True, timeout, type_)
        conn.worker_gr = greenlet_pool.spawn(self._connection_attached, conn)
        conn.worker_gr.link_exception(conn.close)
        return conn
