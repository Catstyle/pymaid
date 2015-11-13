__all__ = ['Channel']

import os
from _socket import socket as realsocket
from _socket import AF_UNIX, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR

import six
from copy import weakref

from gevent.socket import error as socket_error, EWOULDBLOCK
from gevent.core import READ
from gevent.hub import get_hub

from pymaid.connection import Connection
from pymaid.utils import greenlet_pool, pymaid_logger_wrapper

range = six.moves.range
string_types = six.string_types
del six


@pymaid_logger_wrapper
class Channel(object):

    # Sets the maximum number of consecutive accepts that a process may perform
    # on a single wake up. High values give higher priority to high connection
    # rates, while lower values give higher priority to already established
    # connections.
    # Default is 256. Note, that in case of multiple working processes on the
    # same listening value, it should be set to a lower value.
    # (pywsgi.WSGIServer sets it to 1 when environ["wsgi.multiprocess"] is true)
    MAX_ACCEPT = 256
    MAX_BACKLOG = 1024
    MAX_CONCURRENCY = 50000

    CONNECTION_CLASS = Connection

    def __init__(self, loop=None):
        self.loop = loop or get_hub().loop
        self.clients = weakref.WeakValueDictionary()
        self.is_bound = False

    def _do_accept(self, sock, max_accept=MAX_ACCEPT):
        accept, attach = sock.accept, self._connection_attached
        bind = self._bind_connection_handler
        ConnectionClass = self.CONNECTION_CLASS
        for _ in range(max_accept):
            if self.is_full:
                return
            try:
                peer_socket, address = accept()
            except socket_error as ex:
                if ex.errno == EWOULDBLOCK:
                    return
                self.logger.exception(ex)
                raise
            conn = ConnectionClass(self, sock=peer_socket, server_side=True)
            bind(conn)
            attach(conn)

    def _bind_connection_handler(self, conn):
        self.logger.info(
            '[conn|%d][host|%s][peer|%s] made',
            conn.conn_id, conn.sockname, conn.peername
        )
        conn.s_gr = greenlet_pool.spawn(self.connection_handler, conn)
        conn.s_gr.link_exception(conn.close)

    def _connection_attached(self, conn):
        conn.set_close_cb(self._connection_detached)
        assert conn.conn_id not in self.clients
        self.clients[conn.conn_id] = conn
        self.connection_attached(conn)

    def _connection_detached(self, conn, reason=None):
        conn.s_gr.kill(block=False)
        assert conn.conn_id in self.clients
        del self.clients[conn.conn_id]
        self.connection_detached(conn, reason)

    @property
    def is_full(self):
        return len(self.clients) >= self.MAX_CONCURRENCY

    def listen(self, address, type_=SOCK_STREAM, backlog=MAX_BACKLOG):
        if self.is_bound:
            self.logger.warn(
                '%s wants to listen on %s while already bound %s',
                self.__class__.__name__, address, self.listener.getsockname()
            )
            return
        self.is_bound = True
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
        self.listener = sock
        self.accept_watcher = self.loop.io(sock.fileno(), READ)

    def connect(self, address, family=AF_INET, type_=SOCK_STREAM, timeout=None):
        if isinstance(address, string_types):
            family = AF_UNIX
        conn = self.CONNECTION_CLASS(
            self, family=family, type_=type_, server_side=False
        )
        conn.connect(address, timeout)
        self._bind_connection_handler(conn)
        return conn

    def connection_attached(self, conn):
        pass

    def connection_detached(self, conn, reason=None):
        pass

    def connection_handler(self, conn):
        '''
        Automatically called by connection once made
        it will run in an independent greenlet
        '''
        pass

    def start(self):
        if not self.accept_watcher.active:
            self.accept_watcher.start(
                self._do_accept, self.listener, self.MAX_ACCEPT
            )

    def stop(self):
        if self.accept_watcher.active:
            self.accept_watcher.stop()
