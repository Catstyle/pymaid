import ssl as _ssl

from typing import Optional, Sequence, Type, Tuple, Union

from google.protobuf.service_reflection import GeneratedServiceType

from pymaid import create_stream, create_unix_stream
from pymaid import create_stream_server, create_unix_stream_server
from pymaid.ext.middleware import MiddlewareManager
from pymaid.net import TransportType, Stream
from pymaid.rpc.channel import Channel, ConnectionType
from pymaid.utils.functional import listify
from pymaid.utils.logger import logger_wrapper

from .connection import Connection
from .protocol import Protocol, Handler, ServiceRepository

__all__ = ['StreamChannel', 'UnixStreamChannel']


@logger_wrapper
class Channel(Channel):

    def __init__(
        self,
        services: Optional[Union[Sequence[GeneratedServiceType], ServiceRepository]] = None,
        *,
        name: str = 'PBChannel',
        middleware_manager: Optional[MiddlewareManager] = None,
        close_conn_onerror: bool = True,
        connection_class: ConnectionType = Connection,
        protocol_class: Type[Protocol] = Protocol,
        handler_class: Type[Handler] = Handler,
    ):
        super().__init__(name, connection_class, middleware_manager)
        self.close_conn_onerror = close_conn_onerror
        self.protocol_class = protocol_class
        self.handler_class = handler_class

        self.server = None
        if not isinstance(services, ServiceRepository):
            services = ServiceRepository(listify(services))
        self.service_repository = services

    def make_connection(self, transport: 'TransportType'):
        return self.connection_class(
            transport,
            self.protocol_class(),
            self.handler_class(self.service_repository),
        )

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
            lambda: transport_class(server=self, client_side=False),
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
            lambda: transport_class(server=self, client_side=True),
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
            lambda: transport_class(server=self, client_side=False),
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
            lambda: transport_class(server=self, client_side=True),
            path=address,
            ssl=ssl,
            server_hostname=server_hostname,
            ssl_handshake_timeout=ssl_handshake_timeout,
        )
        return transport.conn
