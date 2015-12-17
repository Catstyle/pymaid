__all__ = ['ServerChannel', 'ClientChannel']

import os
from copy import weakref
from _socket import socket as realsocket
from _socket import AF_UNIX, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR

from six import itervalues, string_types
from gevent.socket import error as socket_error, EWOULDBLOCK
from gevent.core import READ

from pymaid.connection import Connection
from pymaid.error.base import BaseEx
from pymaid.utils import greenlet_pool, pymaid_logger_wrapper, io


@pymaid_logger_wrapper
class BaseChannel(object):

    MAX_CONCURRENCY = 50000

    def __init__(self, handler, connection_class=Connection):
        self.handler = handler
        self.handler_args = ()
        self.connection_class = connection_class
        self.connections = weakref.WeakValueDictionary()

    def _connection_attached(self, conn):
        self.logger.info(
            '[conn|%d][host|%s][peer|%s] made',
            conn.connid, conn.sockname, conn.peername
        )
        assert conn.connid not in self.connections
        self.connections[conn.connid] = conn
        conn.set_close_cb(self._connection_detached)
        conn.worker_gr = greenlet_pool.spawn(
            self.handler, conn, *self.handler_args
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
    # (pywsgi.WSGIServer sets it to 1 when environ["wsgi.multiprocess"] is true)
    MAX_ACCEPT = 256

    def __init__(self, handler, listener=None, connection_class=Connection,
                 close_conn_onerror=True):
        super(ServerChannel, self).__init__(handler, connection_class)
        self.handler_args = (listener,)
        self.close_conn_onerror = close_conn_onerror
        self.accept_watchers = []

    def _do_accept(self, sock, max_accept):
        accept, attach_connection = sock.accept, self._connection_attached
        ConnectionClass = self.connection_class
        cnt = 0
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
            attach_connection(ConnectionClass(peer_socket))

    def listen(self, address, backlog=1024, type_=SOCK_STREAM):
        # not support ipv6 yet
        if isinstance(address, string_types):
            family = AF_UNIX
            if os.path.exists(address):
                os.unlink(address)
        else:
            family = AF_INET
        sock = realsocket(family, type_)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.bind(address)
        sock.listen(backlog)
        sock.setblocking(0)
        self.accept_watchers.append((io(sock.fileno(), READ), sock))

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

    def __init__(self, address, handler, connection_class=Connection):
        super(ClientChannel, self).__init__(handler, connection_class)
        self.address = address
        self.family = AF_INET
        if isinstance(address, string_types):
            self.family = AF_UNIX

    def connect(self, type_=SOCK_STREAM, timeout=None):
        conn = self.connection_class.connect(
            self.address, timeout, self.family, type_
        )
        self._connection_attached(conn)
        return conn
