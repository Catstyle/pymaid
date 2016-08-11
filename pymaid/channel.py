__all__ = ['ServerChannel', 'ClientChannel']

import os
from copy import weakref
from _socket import socket as realsocket
from _socket import (
    AF_UNIX, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, SO_REUSEPORT
)

from six import itervalues, string_types
from gevent.socket import error as socket_error, EWOULDBLOCK
from gevent.core import READ

from pymaid.connection import Connection
from pymaid.error.base import BaseEx
from pymaid.utils import greenlet_pool, pymaid_logger_wrapper, io


@pymaid_logger_wrapper
class BaseChannel(object):

    MAX_CONCURRENCY = 50000

    def __init__(self, handler, connection_class=Connection, **kwargs):
        self.parser = None
        self.handler = handler
        self.handler_kwargs = kwargs
        self.connection_class = connection_class
        self.connections = weakref.WeakValueDictionary()

    def _connection_attached(self, conn, **handler_kwargs):
        self.logger.info(
            '[conn|%d][host|%s][peer|%s] made',
            conn.connid, conn.sockname, conn.peername
        )
        assert conn.connid not in self.connections
        self.connections[conn.connid] = conn
        conn.add_close_cb(self._connection_detached)
        if self.parser:
            # used by stub
            conn.pack_meta = self.parser.pack_meta
            conn.unpack = self.parser.unpack
        conn.worker_gr = greenlet_pool.spawn(
            self.handler, conn, **handler_kwargs
        )
        conn.worker_gr.link_exception(conn.close)
        self.connection_attached(conn)

    def _connection_detached(self, conn, reason=None, reset=False):
        log = self.logger.info
        if reason:
            if reset or isinstance(reason, (BaseEx, string_types)):
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
        return len(self.connections) >= self.MAX_CONCURRENCY

    def connection_attached(self, conn):
        pass

    def connection_detached(self, conn, reason=None):
        pass

    def stop(self, reason='Channel calls stop'):
        for conn in itervalues(self.connections):
            conn.delay_close(reason)


@pymaid_logger_wrapper
class ServerChannel(BaseChannel):

    # Sets the maximum number of consecutive accepts that a process may perform
    # on a single wake up. High values give higher priority to high connection
    # rates, while lower values give higher priority to already established
    # connections.
    # Default is 256. Note, that in case of multiple working processes on the
    # same listening value, it should be set to a lower value.
    MAX_ACCEPT = 256

    def __init__(self, handler, listener=None, connection_class=Connection,
                 **kwargs):
        super(ServerChannel, self).__init__(handler, connection_class, **kwargs)
        self.parser = kwargs.pop('parser', None)
        self.handler_kwargs.update({'listener': listener})
        self.accept_watchers = []
        self.middlewares = []

    def _do_accept(self, sock, max_accept):
        accept, attach_connection = sock.accept, self._connection_attached
        ConnectionClass = self.connection_class
        cnt, handler_kwargs = 0, self.handler_kwargs
        while 1:
            if cnt >= max_accept or self.is_full:
                break
            cnt += 1
            try:
                peer_socket, address = accept()
            except socket_error as ex:
                if ex.errno == EWOULDBLOCK:
                    break
                self.logger.exception(ex)
                raise
            attach_connection(ConnectionClass(peer_socket), **handler_kwargs)

    def _connection_attached(self, conn, **handler_kwargs):
        super(ServerChannel, self)._connection_attached(conn, **handler_kwargs)
        for middleware in self.middlewares:
            middleware.on_connect(conn)

    def _connection_detached(self, conn, reason=None, reset=False):
        super(ServerChannel, self)._connection_detached(conn, reason, reset)
        for middleware in self.middlewares:
            middleware.on_close(conn)

    def listen(self, address, backlog=1024, type_=SOCK_STREAM):
        # not support ipv6 yet
        if isinstance(address, string_types):
            family = AF_UNIX
            if os.path.exists(address):
                os.unlink(address)
        else:
            family = AF_INET
        self.logger.info(
            '[listening|%s][type|%s][backlog|%d]', address, type_, backlog
        )
        sock = realsocket(family, type_)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.setsockopt(SOL_SOCKET, SO_REUSEPORT, 1)
        sock.bind(address)
        sock.listen(backlog)
        sock.setblocking(0)
        self.accept_watchers.append((io(sock.fileno(), READ), sock))

    def append_middleware(self, middleware):
        self.middlewares.append(middleware)

    def start(self):
        for watcher, sock in self.accept_watchers:
            if not watcher.active:
                watcher.start(self._do_accept, sock, self.MAX_ACCEPT)

    def stop(self, reason='ServerChannel calls stop'):
        for watcher, sock in self.accept_watchers:
            if watcher.active:
                watcher.stop()
        super(ServerChannel, self).stop(reason)


@pymaid_logger_wrapper
class ClientChannel(BaseChannel):

    def __init__(self, handler=lambda *args, **kwargs: '',
                 connection_class=Connection, **kwargs):
        super(ClientChannel, self).__init__(handler, connection_class, **kwargs)
        self.parser = kwargs.pop('parser', None)

    def connect(self, address, type_=SOCK_STREAM, timeout=None, **kwargs):
        family = AF_UNIX if isinstance(address, string_types) else AF_INET
        conn = self.connection_class.connect(address, timeout, family, type_)
        handler_kwargs = self.handler_kwargs.copy()
        handler_kwargs.update(kwargs)
        self._connection_attached(conn, **handler_kwargs)
        return conn
