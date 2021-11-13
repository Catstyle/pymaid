import ssl as _ssl

from typing import Optional, Tuple, Type, TypeVar, Union

from pymaid.ext.middleware import MiddlewareManager
from pymaid.net.channel import StreamChannel as NetStreamChannel
from pymaid.ext.handler import SerialHandler
from pymaid.net.protocol import Protocol, ProtocolType
from pymaid.types import HandlerType
from pymaid.utils.logger import get_logger

from .connection import Connection, ConnectionType
from .context import ContextManager
from .router import Router

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
        name: str = 'RPCChannel',
        address: Union[Tuple[str, int], str] = '',
        transport_class: ConnectionType = Connection,
        ssl_context: _ssl.SSLContext,
        ssl_handshake_timeout: Optional[float] = None,
        protocol_class: ProtocolType = Protocol,
        handler_class: HandlerType = SerialHandler,
        router_class: Type[Router] = Router,
        context_manager_class: Type[ContextManager] = ContextManager,
        middleware_manager: Optional[MiddlewareManager] = None,
    ):
        super().__init__(
            name=name,
            address=address,
            transport_class=transport_class,
            ssl_context=ssl_context,
            ssl_handshake_timeout=ssl_handshake_timeout,
            middleware_manager=middleware_manager,
        )

        self.protocol_class = protocol_class
        self.handler_class = handler_class
        self.router = router_class()
        self.context_manager_class = context_manager_class

    def _make_connection(
        self,
        sock,
        initiative,
        on_open=None,
        on_close=None,
    ) -> ConnectionType:
        return self.transport_class(
            sock,
            initiative=initiative,
            ssl_context=self.ssl_context,
            ssl_handshake_timeout=self.ssl_handshake_timeout,
            on_open=on_open,
            on_close=on_close,
            protocol=self.protocol_class,
            handler=self.handler_class(),
            router=self.router,
            context_manager=self.context_manager_class(initiative=False),
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


ChannelType = TypeVar('Channel', bound=Channel)
