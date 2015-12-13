import os
import threading
from contextlib import contextmanager

from gevent.queue import LifoQueue, Full


class ConnectionPool(object):
    """Inspired by redis.ConnectionPool"""

    def __init__(self, name, channel, max_connections=50, queue_class=LifoQueue,
                 **connection_kwargs):
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
        self.queue_class = queue_class
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
                self.pool.put_nowait(None)
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
        connection = self.pool.get(block=True, timeout=timeout)
        if connection is None:
            connection = self.make_connection()
        return connection

    def make_connection(self):
        "Create a new connection"
        connection = self.channel.connect(**self.connection_kwargs)
        connection.pid = os.getpid()
        self._connections.append(connection)
        def release():
            self.release(connection)
        connection.release = release
        return connection

    def release(self, connection):
        "Releases the connection back to the pool"
        self._checkpid()
        if connection.pid != self.pid or connection.is_closed:
            return
        try:
            self.pool.put_nowait(connection)
        except Full:
            # perhaps the pool has been reset() after a fork? regardless,
            # we don't want this connection
            pass

    def disconnect(self):
        "Disconnects all connections in the pool"
        for connection in self._connections:
            connection.release = None
            connection.close()

    def __repr__(self):
        return "ConnectionPool of %s: [connect_kwargs|%s][created|%d]" % (
            self.name, self.connection_kwargs, len(self._connections)
        )


@contextmanager
def release(conn):
    try:
        yield conn
    finally:
        conn.release()
