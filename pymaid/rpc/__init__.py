import socket
import ssl as _ssl
from typing import Optional, Sequence, Type, Union

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
    address: str,
    *,
    name: str = 'StreamChannel',
    channel_class: channel.ChannelType = channel.Channel,
    transport_class: connection.ConnectionType = connection.Connection,
    family: socket.AddressFamily = socket.AF_UNSPEC,
    flags: socket.AddressInfo = socket.AI_PASSIVE,
    backlog: int = 4096,
    reuse_address: bool = True,
    reuse_port: bool = False,
    ssl_context: Union[None, bool, '_ssl.SSLContext'] = None,
    ssl_handshake_timeout: Optional[float] = None,
    start_serving: bool = True,
    middleware_manager: Optional[MiddlewareManager] = None,
    protocol: Type[ProtocolType] = Protocol,
    handler_class: Optional[Type[handler.Handler]] = handler.SerialHandler,
    router_class: Type[router.Router] = router.Router,
    services: Optional[Sequence[ServiceType]] = None,
    router: Optional[router.Router] = None,
):
    assert services is not None or router, 'should provide services or router'
    ch = channel_class(
        name=name,
        transport_class=transport_class,
        ssl_context=ssl_context,
        ssl_handshake_timeout=ssl_handshake_timeout,
        middleware_manager=middleware_manager,
        protocol=protocol,
        handler_class=handler_class,
        router_class=router_class,
    )
    if services:
        ch.router.include_services(services)
    if router:
        ch.router.include_router(router)
    await ch.listen(
        address,
        family=family,
        flags=flags,
        backlog=backlog,
        reuse_address=reuse_address,
        reuse_port=reuse_port,
    )
    if start_serving:
        ch.start()
    return ch
