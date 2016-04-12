import os
import threading
from contextlib import contextmanager
from _socket import error as socket_error

from gevent.queue import PriorityQueue, Full


class ConnectionPool(object):
    """Inspired by redis.ConnectionPool"""

    queue_class = PriorityQueue

    def __init__(self, name, channel, max_connections=50, **connection_kwargs):
        """
        Create a blocking connection pool.

        Use ``max_connections`` to increase / decrease the pool size::

        By default, connections will be created by channel.connect method.

        Any additional keyword arguments are passed to the channel.connect.
        """
        max_connections = max_connections or 2 ** 31
        if not isinstance(max_connections, (int, long)) or max_connections < 0:
            raise ValueError('"max_connections" must be a positive integer')

        self.name = name
        self.max_connections = max_connections
        self.empty_item = (10000, None)
        self.channel = channel
        self.connection_kwargs = connection_kwargs
        self.reset()

    def _checkpid(self):
        if self.pid != os.getpid():
            with self._check_lock:
                if self.pid == os.getpid():
                    # another thread already did the work while we waited
                    # on the lock.
                    return
                self.disconnect()
                self.reset()

    def reset(self):
        self.pid = os.getpid()
        self._check_lock = threading.Lock()

        # Create and fill up a thread safe queue with ``None`` values.
        self.pool = self.queue_class(self.max_connections)
        while 1:
            try:
                self.pool.put_nowait(self.empty_item)
            except Full:
                break

        # Keep a list of actual connection instances so that we can
        # disconnect them later.
        self._connections = []

    def get_connection(self, timeout=None):
        """
        Get a connection from the pool, blocking for ``timeout`` util
        a connection is available from the pool.
        """
        self._checkpid()
        # will raise Empty if timeout is not None, so just raise to upper level
        item = self.pool.get(block=True, timeout=timeout)
        if item is self.empty_item:
            connection = self.make_connection()
        else:
            connection = item[1]
        return connection
    
    @contextmanager
    def get_autorelease_connection(self, timeout=None):
        conn = self.get_connection(timeout)
        try:
            yield conn
        finally:
            self.release(conn)

    def make_connection(self):
        "Create a new connection"
        try:
            connection = self.channel.connect(**self.connection_kwargs)
            connection.pid = os.getpid()
            connection.add_close_cb(self.release)
            def release():
                self.release(connection)
            connection.release = release
            self._connections.append(connection)
        except socket_error:
            connection = None
        return connection

    def release(self, connection, *args):
        "Releases the connection back to the pool"
        self._checkpid()
        if connection.pid != self.pid:
            return

        if connection.is_closed:
            if connection in self._connections:
                self._connections.remove(connection)
            connection = None
            item = self.empty_item
        else:
            item = (len(connection.transmissions), connection)
        try:
            self.pool.put_nowait(item)
        except Full:
            # perhaps the pool has been reset() after a fork? regardless,
            # we don't want this connection
            # should we close this conn?
            if connection:
                connection.close('useless')

    def disconnect(self, reason=None):
        "Disconnects all connections in the pool"
        for connection in self._connections[:]:
            connection.close(reason)

    def __repr__(self):
        return "[ConnectionPool|%s][connect_kwargs|%s][max|%d][created|%d]" % (
            self.name, self.connection_kwargs,
            self.max_connections, len(self._connections)
        )
    __str__ = __repr__
