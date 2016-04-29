import os
import threading
from contextlib import contextmanager
from _socket import error as socket_error

from gevent.queue import LifoQueue, PriorityQueue, Full, Empty


class ConnectionPool(object):
    """Inspired by redis.ConnectionPool"""

    queue_class = LifoQueue
    empty_item = None

    def __init__(self, name, size=50, channel=None, **connection_kwargs):
        """
        Create a blocking connection pool.

        Use ``size`` to increase / decrease the pool size::

        By default, connections will be created by channel.connect method.

        Any additional keyword arguments are passed to the channel.connect.
        """
        size = size or 2 ** 31
        if not isinstance(size, (int, long)) or size < 0:
            raise ValueError('"size" must be a positive integer')

        self.name = name
        self.size = size
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

        # Create and fill up a thread safe queue with ``empty_item`` values.
        self.pool = self.queue_class(self.size)
        while 1:
            try:
                self.pool.put_nowait(self.empty_item)
            except Full:
                break

        # Keep a list of actual connection instances so that we can
        # disconnect them later.
        self._connections = []

    def item_getter(self, item):
        return item

    def item_putter(self, conn):
        return conn

    def initpool(self, init_count):
        if self._connections:
            # do not init pool if there are connections
            return
        if init_count > self.size:
            raise ValueError('init_count should not greater than pool size')
        if not self.channel:
            raise AssertionError('calling initpool with channel is None')
        try:
            for _ in range(init_count):
                self.pool.get_nowait()
        except Empty:
            pass
        try:
            for _ in range(init_count):
                conn = self.make_connection()
                self.pool.put_nowait(self.item_putter(conn))
        except Full:
            pass

    def get_connection(self, timeout=None):
        """
        Get a connection from the pool, blocking for ``timeout`` util
        a connection is available from the pool.
        """
        self._checkpid()
        # will raise Empty if timeout is not None, so just raise to upper level
        item = self.pool.get(block=True, timeout=timeout)
        if item is self.empty_item:
            return self.make_connection()
        else:
            return self.item_getter(item)

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

    def release(self, connection):
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
            item = self.item_putter(connection)
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
            self.name, self.connection_kwargs, self.size, len(self._connections)
        )
    __str__ = __repr__


class PriorityPool(ConnectionPool):

    queue_class = PriorityQueue
    empty_item = (10000, None)

    def item_getter(self, item):
        return item[1]

    def item_putter(self, conn):
        return (conn.transmission_id, conn)
