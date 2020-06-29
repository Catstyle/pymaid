from typing import Any, Optional, TypeVar

from pymaid.conf import settings
from pymaid.ext.middleware import MiddlewareManager
from pymaid.net import TransportType
from pymaid.utils.logger import logger_wrapper

from .error import RPCError

__all__ = ['Channel']


@logger_wrapper
class Connection:
    '''Connection represent a communication way for client <--> server

    It holds transport and channel.
    '''

    def __init__(self, transport: TransportType):
        self.transport = transport
        self.is_closed = False

    def feed_data(self, data: bytes, addr=None) -> Any:
        raise NotImplementedError

    def shutdown(self):
        self.transport.shutdown()

    def close(self, exc: Optional[Exception] = None):
        if self.is_closed:
            return
        self.is_closed = True
        self.transport.close(exc)
        # break cyclic
        self.transport = None

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} transport={self.transport}>'


@logger_wrapper
class Channel:

    CONN_ID = 0

    def __init__(
        self,
        name: str = 'Channel',
        connection_class: 'ConnectionType' = Connection,
        middleware_manager: Optional[MiddlewareManager] = None,
    ):
        self.name = name
        self.connection_class = connection_class
        self.connections = {}
        self.middleware_manager = middleware_manager or MiddlewareManager()
        self.is_paused = False
        self.is_stopped = False

    @property
    def is_full(self):
        return len(self.connections) >= settings.get('MAX_CONNECTIONS', ns='pymaid')

    def make_connection(self, transport: 'TransportType') -> Connection:
        return self.connection_class(transport, self)

    def connection_made(self, transport: 'TransportType') -> Connection:
        # connection_made is called within loop.call_later
        # raise an error will not terminate correctly, just close conn
        if self.is_paused:
            transport.close(RPCError.ServerPaused())
            return
        if self.is_full:
            transport.close(RPCError.ConnectionLimit())
            return

        conn = self.make_connection(transport)
        self.CONN_ID = self.CONN_ID + 1
        conn.conn_id = f'{self.name}-{self.CONN_ID}'
        assert conn.conn_id not in self.connections
        self.connections[conn.conn_id] = conn
        self.middleware_manager.dispatch('on_connect', self, conn)
        return conn

    def connection_lost(
        self,
        conn: 'ConnectionType',
        exc: Optional[Exception] = None
    ):
        # if rejected by concurrency limition, should not call this connection_lost
        assert conn.conn_id in self.connections
        # safe to call conn.close
        conn.close()
        self.middleware_manager.dispatch('on_close', self, conn)
        # full = self.is_full
        del self.connections[conn.conn_id]
        # if (full
        #         and not self.is_full
        #         and not self.is_paused
        #         and not self.is_stopped
        #         and self.middleware_manager.dispatch('can_accept', self)):
        #     self.start()

    async def start(self):
        self.is_paused = False
        self.middleware_manager.dispatch('on_start', self)

    async def pause(self, reason: str = ''):
        self.is_paused = True
        self.middleware_manager.dispatch('on_pause', self)

    async def stop(self, reason: str = 'stop'):
        if self.is_stopped:
            return
        self.is_stopped = True

        if not self.is_paused:
            self.pause(reason)
        for conn in self.connections.values():
            conn.close(reason)
        self.middleware_manager.dispatch('on_stop', self)


ConnectionType = TypeVar('Connection', bound=Connection)
ChannelType = TypeVar('Channel', bound=Channel)
