import ssl as _ssl

from functools import partial
from typing import Any, Optional, Tuple, Type, TypeVar, Union

from pymaid import create_stream, create_unix_stream
from pymaid import create_stream_server, create_unix_stream_server
from pymaid.conf import settings
from pymaid.ext.middleware import MiddlewareManager
from pymaid.net import TransportType, Stream, Protocol, ProtocolType
from pymaid.utils.logger import logger_wrapper

from .error import RPCError
from .handler import Handler, SerialHandler
from .router import Router
from .types import HandlerType

__all__ = ['Channel', 'StreamChannel', 'UnixStreamChannel']


@logger_wrapper
class Connection:
    '''Connection represent a communication way for client <--> server

    It holds the low level transport.
    '''

    def __init__(self, transport: TransportType):
        self.transport = transport
        self.is_closed = False

    def feed_data(self, data: bytes, addr=None) -> Any:
        '''Received data from low level transport'''
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
    '''Channel manage connections.'''

    CONN_ID = 0

    def __init__(
        self,
        *,
        name: str = 'Channel',
        connection_class: 'ConnectionType' = Connection,
        close_conn_onerror: bool = True,
        protocol_class: Type[Protocol] = Protocol,
        handler_class: Type[Handler] = SerialHandler,
        router_class: Type[Router] = Router,
        middleware_manager: Optional[MiddlewareManager] = None,
    ):
        self.name = name
        self.connection_class = connection_class
        self.connections = {}
        self.middleware_manager = middleware_manager or MiddlewareManager()
        self.is_paused = False
        self.is_stopped = False

        self.server = None
        self.protocol_class = protocol_class
        self.handler_class = handler_class
        self.router = router_class()

    @property
    def is_full(self):
        return len(self.connections) >= settings.pymaid.MAX_CONNECTIONS

    def make_connection(self, transport: 'TransportType') -> Connection:
        return self.connection_class(
            transport,
            self.protocol_class(),
            self.handler_class(self.router),
        )

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
        # if rejected by concurrency limition
        # should not call this connection_lost
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

    async def serve_forever(self):
        if self.server is None:
            raise RuntimeError('server not started')
        await self.server.serve_forever()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.stop(exc_val)
        if exc_val:
            raise exc_val


class StreamChannel(Channel):

    async def listen(
        self,
        address: Tuple[str, int],
        *,
        transport_class: TransportType = Stream,
        backlog: int = 100,
        reuse_address: Optional[bool] = None,
        reuse_port: Optional[bool] = None,
        ssl: Union[None, bool, '_ssl.SSLContext'] = None,
        ssl_handshake_timeout: Optional[float] = None,
        # ssl_shutdown_timeout=None,
    ):
        if self.server is not None:
            raise RuntimeError('server can only call listen once')
        if not isinstance(address, list(list, tuple)) and len(address) != 2:
            raise ValueError('address should be in format of (host, port)')
        if not issubclass(transport_class, Stream):
            raise TypeError('transport_class must be a subclass of Stream')
        self.server = await create_stream_server(
            partial(transport_class, channel=self, initiative=False),
            host=address[0],
            port=address[1],
            backlog=backlog,
            ssl=ssl,
            ssl_handshake_timeout=ssl_handshake_timeout,
            # ssl_shutdown_timeout=ssl_shutdown_timeout,
            reuse_address=reuse_address,
            reuse_port=reuse_port,
        )

    async def connect(
        self,
        address: Tuple[str, int],
        *,
        transport_class: TransportType = Stream,
        ssl: Union[None, bool, '_ssl.SSLContext'] = None,
        server_hostname: Optional[str] = None,
        ssl_handshake_timeout: Optional[float] = None,
        happy_eyeballs_delay: Optional[float] = None,
        interleave: Optional[float] = None,
    ) -> Connection:
        if not isinstance(address, list(list, tuple)) and len(address) != 2:
            raise ValueError('address should be in format of (host, port)')
        if not issubclass(transport_class, Stream):
            raise TypeError('transport_class must be a subclass of Stream')
        transport = await create_stream(
            partial(transport_class, channel=self, initiative=True),
            host=address[0],
            port=address[1],
            ssl=ssl,
            ssl_handshake_timeout=ssl_handshake_timeout,
            server_hostname=server_hostname,
            happy_eyeballs_delay=happy_eyeballs_delay,
            interleave=interleave,
        )
        return transport.conn


class UnixStreamChannel(StreamChannel):

    async def listen(
        self,
        address: str,
        *,
        transport_class: TransportType = Stream,
        backlog: int = 100,
        ssl: Union[None, bool, '_ssl.SSLContext'] = None,
        ssl_handshake_timeout: Optional[float] = None,
        # ssl_shutdown_timeout=None,
    ):
        if self.server is not None:
            raise RuntimeError('server can only call listen once')
        if not issubclass(transport_class, Stream):
            raise TypeError('transport_class must be a subclass of Stream')
        self.server = await create_unix_stream_server(
            partial(transport_class, channel=self, initiative=False),
            path=address,
            backlog=backlog,
            ssl=ssl,
            ssl_handshake_timeout=ssl_handshake_timeout,
            # ssl_shutdown_timeout=ssl_shutdown_timeout,
        )

    async def connect(
        self,
        address: str,
        *,
        transport_class: TransportType = Stream,
        ssl: Union[None, bool, '_ssl.SSLContext'] = None,
        server_hostname: Optional[str] = None,
        ssl_handshake_timeout: Optional[float] = None,
    ) -> Connection:
        if not issubclass(transport_class, Stream):
            raise TypeError('transport_class must be a subclass of Stream')
        transport = await create_unix_stream(
            partial(transport_class, channel=self, initiative=True),
            path=address,
            ssl=ssl,
            server_hostname=server_hostname,
            ssl_handshake_timeout=ssl_handshake_timeout,
        )
        return transport.conn


ConnectionType = TypeVar('Connection', bound=Connection)
ChannelType = TypeVar('Channel', bound=Channel)


def create_stream_channel(
    address: Union[Tuple[str, int], str],
    *,
    name: str = 'StreamChannel',
    connection_class: ConnectionType = Connection,
    middleware_manager: Optional[MiddlewareManager] = None,
    close_conn_onerror: bool = True,
    protocol_class: ProtocolType = Stream,
    handler_class: Optional[Type[HandlerType]] = SerialHandler,
    router_class: Optional[Type[Router]] = Router,
) -> ChannelType:
    if isinstance(address, str):
        channel_cls = UnixStreamChannel
    else:
        channel_cls = StreamChannel
    return channel_cls(
        name=name,
        connection_class=connection_class,
        close_conn_onerror=close_conn_onerror,
        middleware_manager=middleware_manager,
        protocol_class=protocol_class,
        handler_class=handler_class,
        router_class=router_class,
    )
