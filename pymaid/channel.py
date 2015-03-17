__all__ = ['Channel']

import socket
import _socket
from _socket import socket as realsocket

import six
from copy import weakref

from gevent.socket import error as socket_error, EWOULDBLOCK
from gevent.core import READ
from gevent.hub import get_hub

from pymaid.connection import Connection
from pymaid.utils import pymaid_logger_wrapper

range = six.moves.range
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
        for _ in range(self.MAX_ACCEPT):
            if self.is_full:
                return
            try:
                peer_socket, address = sock.accept()
            except socket_error as ex:
                if ex.errno == EWOULDBLOCK:
                    return
                self.logger.exception(ex)
                raise
            self._new_connection(peer_socket, server_side=True)

    def _new_connection(self, sock, server_side, ignore_heartbeat=False):
        conn = Connection(self, sock, server_side)
        conn.set_close_cb(self.connection_closed)
        if server_side:
            assert conn.conn_id not in self.incoming_connections
            self.incoming_connections[conn.conn_id] = conn
        else:
            assert conn.conn_id not in self.outgoing_connections
            self.outgoing_connections[conn.conn_id] = conn
        self.logger.debug(
            '[conn|%d][host|%s][peer|%s] made',
            conn.conn_id, conn.sockname, conn.peername
        )
        self.connection_made(conn)
        return conn

    @property
    def is_full(self):
        return len(self.incoming_connections) >= self.MAX_CONCURRENCY

    def connect(self, host, port, timeout=None, ignore_heartbeat=False):
        sock = socket.create_connection((host, port), timeout=timeout)
        conn = self._new_connection(sock, False, ignore_heartbeat)
        return conn

    def listen(self, host, port, backlog=MAX_BACKLOG):
        sock = realsocket(_socket.AF_INET, _socket.SOCK_STREAM, 0)
        sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(backlog)
        sock.setblocking(0)
        accept_watcher = self.loop.io(sock.fileno(), READ)
        self.listeners.append((sock, accept_watcher))

    def connection_made(self, conn):
        pass

    def connection_closed(self, conn, reason=None):
        pass

    def connection_handler(self, conn):
        '''automatically called by connection once made,
        it will run in an independent greenlet'''
        pass

    def start(self):
        [io.start(self._do_accept, s) for s, io in self.listeners if not io.active]

    def stop(self):
        [io.stop() for _, io in self.listeners if io.active]
