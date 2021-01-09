import ssl as _ssl
from typing import Optional, Sequence, Tuple, Type, Union

from pymaid.ext.middleware import MiddlewareManager
from pymaid.net.protocol import ProtocolType
from pymaid.rpc.channel import create_stream_channel
from pymaid.rpc.connection import Connection, ConnectionType
from pymaid.rpc.types import ServiceType

from . import context
from . import handler
from . import protocol
from . import router

__all__ = ('connection', 'context', 'handler', 'protocol')


async def dial_stream(
    address: Union[Tuple[str, int], str],
    *,
    name: str = 'StreamChannel',
    transport_class: ConnectionType = Connection,
    ssl_context: Union[None, bool, '_ssl.SSLContext'] = None,
    ssl_handshake_timeout: Optional[float] = None,
    close_conn_onerror: bool = True,
    protocol: protocol.Protocol = protocol.Protocol,
    handler_class: Type[handler.Handler] = handler.PBSerialHandler,
    router_class: Type[router.Router] = router.PBRouter,
    middleware_manager: Optional[MiddlewareManager] = None,
):
    return create_stream_channel(
        address,
        name=name,
        transport_class=transport_class,
        ssl_context=ssl_context,
        ssl_handshake_timeout=ssl_handshake_timeout,
        close_conn_onerror=close_conn_onerror,
        protocol=protocol,
        handler_class=handler_class,
        router_class=router_class,
        middleware_manager=middleware_manager,
    )


async def serve_stream(
    address: Union[Tuple[str, int], str],
    *,
    name: str = 'StreamChannel',
    transport_class: ConnectionType = Connection,
    backlog: int = 128,
    ssl_context: Union[None, bool, '_ssl.SSLContext'] = None,
    ssl_handshake_timeout: Optional[float] = None,
    middleware_manager: Optional[MiddlewareManager] = None,
    close_conn_onerror: bool = True,
    protocol: ProtocolType = protocol.Protocol,
    handler_class: Type[handler.Handler] = handler.PBSerialHandler,
    router_class: Type[router.Router] = router.PBRouter,
    services: Optional[Sequence[ServiceType]] = None,
    router: Optional[router.Router] = None,
):
    assert services is not None or router, 'should provide services or router'
    ch = create_stream_channel(
        address,
        name=name,
        transport_class=transport_class,
        ssl_context=ssl_context,
        ssl_handshake_timeout=ssl_handshake_timeout,
        middleware_manager=middleware_manager,
        close_conn_onerror=close_conn_onerror,
        protocol=protocol,
        handler_class=handler_class,
        router_class=router_class,
    )
    if services:
        ch.router.include_services(services)
    if router:
        ch.router.include_router(router)
    await ch.listen(address, backlog=backlog)
    ch.start()
    async with ch:
        await ch.serve_forever()


def implall(service):
    service_name = service.DESCRIPTOR.name
    missing = []
    for base in service.__bases__:
        for method in base.DESCRIPTOR.methods:
            method_name = method.name
            base_method = getattr(base, method_name)
            impl_method = getattr(service, method_name, base_method)
            if base_method == impl_method:
                missing.append(f'{service_name}.{method_name}')
    if missing:
        raise RuntimeError(f'{missing} are not implemented')
    return service
