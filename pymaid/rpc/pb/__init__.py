import ssl as _ssl
from typing import Optional, Sequence, Tuple, Type, Union

from pymaid.ext.middleware import MiddlewareManager
from pymaid.net import ProtocolType
from pymaid.rpc.channel import create_stream_channel
from pymaid.rpc.types import ConnectionType, ServiceType

from . import connection
from . import handler
from . import protocol
from . import router

__all__ = ('connection', 'handler', 'protocol')


async def call_stream(
    address: Union[Tuple[str, int], str],
    *,
    name: str = 'StreamChannel',
    connection_class: ConnectionType = connection.Connection,
    close_conn_onerror: bool = True,
    middleware_manager: Optional[MiddlewareManager] = None,
    protocol_class: Type[ProtocolType] = protocol.Protocol,
    handler_class: Type[handler.Handler] = handler.PBSerialHandler,
    router_class: Type[router.Router] = router.PBRouter,
    ssl: Union[None, bool, '_ssl.SSLContext'] = None,
):
    return create_stream_channel(
        address,
        name=name,
        connection_class=connection_class,
        close_conn_onerror=close_conn_onerror,
        middleware_manager=middleware_manager,
        protocol_class=protocol_class,
        handler_class=handler_class,
        router_class=router_class,
    )


async def serve_stream(
    address: Union[Tuple[str, int], str],
    *,
    name: str = 'StreamChannel',
    connection_class: ConnectionType = connection.Connection,
    close_conn_onerror: bool = True,
    middleware_manager: Optional[MiddlewareManager] = None,
    protocol_class: Type[ProtocolType] = protocol.Protocol,
    handler_class: Type[handler.Handler] = handler.PBSerialHandler,
    router_class: Type[router.Router] = router.PBRouter,
    services: Optional[Sequence[ServiceType]] = None,
    router: Optional[router.Router] = None,
    ssl: Union[None, bool, '_ssl.SSLContext'] = None,
):
    assert services or router, 'should provide services or router'
    ch = create_stream_channel(
        address,
        name=name,
        connection_class=connection_class,
        close_conn_onerror=close_conn_onerror,
        middleware_manager=middleware_manager,
        protocol_class=protocol_class,
        handler_class=handler_class,
        router_class=router_class,
    )
    if services:
        ch.router.include_services(services)
    if router:
        ch.router.include_router(router)
    await ch.listen(address, ssl=ssl)
    await ch.start()
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
