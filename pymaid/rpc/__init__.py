import ssl as _ssl
from typing import Optional, Sequence, Tuple, Type, Union

from pymaid.ext.middleware import MiddlewareManager
from pymaid.net.protocol import Protocol, ProtocolType

from . import channel
from . import connection
from . import handler
from . import pb
from . import router

from .types import ServiceType

__all__ = ('channel', 'connection', 'handler', 'pb', 'router')


async def serve_stream(
    address: Union[Tuple[str, int], str],
    *,
    name: str = 'StreamChannel',
    transport_class: connection.ConnectionType = connection.Connection,
    backlog: int = 128,
    ssl_context: Union[None, bool, '_ssl.SSLContext'] = None,
    ssl_handshake_timeout: Optional[float] = None,
    middleware_manager: Optional[MiddlewareManager] = None,
    close_conn_onerror: bool = True,
    protocol: Type[ProtocolType] = Protocol,
    handler_class: Optional[Type[handler.Handler]] = handler.SerialHandler,
    services: Optional[Sequence[ServiceType]] = None,
    router: Optional[router.Router] = None,
):
    assert services is not None or router, 'should provide services or router'
    ch = channel.create_stream_channel(
        address,
        name=name,
        transport_class=transport_class,
        ssl_context=ssl_context,
        ssl_handshake_timeout=ssl_handshake_timeout,
        middleware_manager=middleware_manager,
        close_conn_onerror=close_conn_onerror,
        protocol=protocol,
        handler_class=handler_class,
    )
    if services:
        ch.router.include_services(services)
    if router:
        ch.router.include_router(router)
    await ch.listen(address, backlog=backlog)
    ch.start()
    async with ch:
        await ch.serve_forever()
