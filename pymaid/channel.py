__all__ = ['Channel']

import os
import _socket
from _socket import socket as realsocket

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
    MAX_BACKLOG = 8192
    MAX_CONCURRENCY = 50000

    def __init__(self, loop=None):
        self.loop = loop or get_hub().loop
        self.listeners = []
        self.incoming_connections = weakref.WeakValueDictionary()
        self.outgoing_connections = weakref.WeakValueDictionary()

    def _do_accept(self, sock):
        accept, attach = sock.accept, self._connection_attached
        for _ in range(self.MAX_ACCEPT):
            if self.is_full:
                return
            try:
                peer_socket, address = accept()
            except socket_error as ex:
                if ex.errno == EWOULDBLOCK:
                    return
                self.logger.exception(ex)
                raise
            conn = Connection(sock=peer_socket, server_side=True)
            attach(conn)

    def _connection_attached(self, conn):
        conn.set_close_cb(self._connection_detached)
        if conn.server_side:
            assert conn.conn_id not in self.incoming_connections
            self.incoming_connections[conn.conn_id] = conn
        else:
            assert conn.conn_id not in self.outgoing_connections
            self.outgoing_connections[conn.conn_id] = conn
        self.logger.info(
            '[conn|%d][host|%s][peer|%s] made',
            conn.conn_id, conn.sockname, conn.peername
        )
        conn.s_gr = greenlet_pool.spawn(self.connection_handler, conn)
        conn.s_gr.link_exception(conn.close)
        self.connection_attached(conn)

    def _connection_detached(self, conn, reason=None):
        conn.s_gr.kill(block=False)
        self.connection_detached(conn, reason)

    @property
    def is_full(self):
        return len(self.incoming_connections) >= self.MAX_CONCURRENCY

    def connect(self, address, family=2, type_=1, timeout=None):
        if isinstance(address, string_types):
            family = 1
        conn = Connection(family=family, type_=type_, server_side=False)
        conn.connect(address, timeout)
        self._connection_attached(conn)
        return conn

    def listen(self, address, type_=1, backlog=MAX_BACKLOG):
        if isinstance(address, string_types):
            try:
                os.unlink(address)
            except OSError:
                if os.path.exists(address):
                    raise
            family = 1
        else:
            family = 2
        sock = realsocket(family, type_)
        sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        sock.bind(address)
        sock.listen(backlog)
        sock.setblocking(0)
        accept_watcher = self.loop.io(sock.fileno(), READ)
        self.listeners.append((sock, accept_watcher))

    def connection_attached(self, conn):
        pass

    def connection_detached(self, conn, reason=None):
        pass

    def connection_handler(self, conn):
        '''automatically called by connection once made,
        it will run in an independent greenlet'''
        pass

    def start(self):
        [io.start(self._do_accept, s) for s, io in self.listeners if not io.active]

    def stop(self):
        [io.stop() for _, io in self.listeners if io.active]
