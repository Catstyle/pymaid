import ssl as _ssl

from typing import Optional, Tuple, Type, TypeVar, Union

from pymaid.ext.middleware import MiddlewareManager
from pymaid.net.channel import StreamChannel as NetStreamChannel
from pymaid.net.protocol import Protocol, ProtocolType
from pymaid.utils.logger import get_logger

from .connection import Connection, ConnectionType
from .handler import Handler, SerialHandler
from .router import Router
from .types import HandlerType, RouterType

__all__ = ('Channel',)

logger = get_logger('rpc')


class Channel(NetStreamChannel):
    '''Channel manage connections.

    RPC *mostly* rely on ordered data, so it should be in stream mode.
    '''

    logger = logger

    def __init__(
        self,
        *,
        name: str = 'Channel',
        address: Union[Tuple[str, int], str] = '',
        stream_class: ConnectionType = Connection,
        ssl_context: _ssl.SSLContext,
        ssl_handshake_timeout: Optional[float] = None,
        close_conn_onerror: bool = True,
        protocol: ProtocolType = Protocol,
        handler_class: Type[Handler] = SerialHandler,
        router_class: Type[Router] = Router,
        middleware_manager: Optional[MiddlewareManager] = None,
    ):
        super().__init__(
            address=address,
            stream_class=stream_class,
            ssl_context=ssl_context,
            ssl_handshake_timeout=ssl_handshake_timeout,
        )
        self.name = name
        self.middleware_manager = middleware_manager or MiddlewareManager()

        self.protocol = protocol
        self.handler_class = handler_class
        self.router = router_class()

    def make_connection(
        self,
        sock,
        initiative,
        on_open=None,
        on_close=None,
    ) -> ConnectionType:
        return self.stream_class(
            sock,
            initiative=initiative,
            ssl_context=self.ssl_context,
            ssl_handshake_timeout=self.ssl_handshake_timeout,
            on_open=on_open,
            on_close=on_close,
            protocol=self.protocol,
            handler=self.handler_class(self.router),
        )

    def connection_made(self, sock) -> ConnectionType:
        conn = super().connection_made(sock)
        self.middleware_manager.dispatch('on_connection_made', self, conn)
        return conn

    def connection_lost(
        self,
        conn: ConnectionType,
        exc: Optional[Exception] = None
    ):
        # full = self.is_full
        super().connection_lost(conn, exc)
        self.middleware_manager.dispatch('on_connection_lost', self, conn)
        # if (full
        #         and not self.is_full
        #         and not self.is_paused
        #         and not self.is_stopped
        #         and self.middleware_manager.dispatch('can_accept', self)):
        #     self.start()

    def start(self):
        super().start()
        self.middleware_manager.dispatch('on_start', self)

    def pause(self, reason: str = ''):
        super().pause(reason)
        self.middleware_manager.dispatch('on_pause', self)

    def shutdown(self, reason: str = 'shutdown'):
        super().shutdown(reason)
        self.middleware_manager.dispatch('on_shutdown', self)

    def close(
        self, reason: Union[None, str, Exception] = 'called close',
    ):
        super().close(reason)
        self.middleware_manager.dispatch('on_close', self)

    def __repr__(self):
        return (
            '<'
            f'{self.name} '
            f'state={self.state.name} '
            f'listeners={len(self.listeners)} '
            f'streams={len(self.streams)} '
            f'middlewares={len(self.middleware_manager.middlewares)}'
            '>'
        )


ChannelType = TypeVar('Channel', bound=Channel)


def create_stream_channel(
    address: Union[Tuple[str, int], str],
    *,
    name: str = 'StreamChannel',
    stream_class: ConnectionType = Connection,
    ssl_context: Union[None, bool, '_ssl.SSLContext'] = None,
    ssl_handshake_timeout: Optional[float] = None,
    close_conn_onerror: bool = True,
    protocol: Protocol = Protocol,
    handler_class: Optional[HandlerType] = SerialHandler,
    router_class: Optional[RouterType] = Router,
    middleware_manager: Optional[MiddlewareManager] = None,
) -> ChannelType:
    return Channel(
        address=address,
        name=name,
        stream_class=stream_class,
        ssl_context=ssl_context,
        ssl_handshake_timeout=ssl_handshake_timeout,
        close_conn_onerror=close_conn_onerror,
        protocol=protocol,
        handler_class=handler_class,
        router_class=router_class,
        middleware_manager=middleware_manager,
    )
