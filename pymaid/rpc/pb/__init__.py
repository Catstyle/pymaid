import ssl as _ssl
from typing import Callable, List, Optional, Type, Union

from pymaid.ext.handler import SerialHandler
from pymaid.ext.middleware import MiddlewareManager
from pymaid.net import dial_stream as raw_dial_stream
from pymaid.net.protocol import ProtocolType
from pymaid.net.stream import Stream
from pymaid.rpc.connection import Connection, ConnectionType
from pymaid.types import HandlerType

from . import context
from . import protocol
from . import router

__all__ = ('connection', 'context', 'protocol')


async def dial_stream(
    address: str,
    *,
    transport_class: ConnectionType = Stream | Connection,
    ssl_context: Union[None, bool, '_ssl.SSLContext'] = None,
    ssl_handshake_timeout: Optional[float] = None,
    on_open: Optional[List[Callable]] = None,
    on_close: Optional[List[Callable]] = None,
    # below are connection kwargs
    protocol_class: protocol.Protocol = protocol.Protocol,
    handler_class: HandlerType = SerialHandler,
    router_class: Type[router.Router] = router.PBRouter,
    context_manager_class: context.ContextManager = context.ContextManager,
    middleware_manager: Optional[MiddlewareManager] = None,
    **kwargs,
):
    return await raw_dial_stream(
        address,
        transport_class=transport_class,
        ssl_context=ssl_context,
        ssl_handshake_timeout=ssl_handshake_timeout,
        protocol=protocol_class(),
        handler=handler_class(),
        router=router_class(),
        context_manager=context_manager_class(initiative=True),
        **kwargs,
    )


async def serve_stream(
    address: str,
    *,
    transport_class: ConnectionType = Stream | Connection,
    protocol_class: ProtocolType = protocol.Protocol,
    handler_class: HandlerType = SerialHandler,
    router_class: Type[router.Router] = router.PBRouter,
    context_manager_class: context.ContextManager = context.ContextManager,
    **kwargs,
):
    from pymaid.rpc import serve_stream as raw_serve_stream
    return await raw_serve_stream(
        address=address,
        transport_class=transport_class,
        protocol_class=protocol_class,
        handler_class=handler_class,
        router_class=router_class,
        context_manager_class=context_manager_class,
        **kwargs,
    )


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
