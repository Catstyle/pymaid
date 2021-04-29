import ssl as _ssl
from typing import Callable, List, Optional, Tuple, Type, Union

from pymaid.ext.middleware import MiddlewareManager
from pymaid.net import dial_stream as raw_dial_stream
from pymaid.net.protocol import ProtocolType
from pymaid.net.stream import Stream
from pymaid.rpc.connection import Connection, ConnectionType

from . import context
from . import handler
from . import protocol
from . import router

__all__ = ('connection', 'context', 'handler', 'protocol')


async def dial_stream(
    address: Union[Tuple[str, int], str],
    *,
    transport_class: ConnectionType = Stream | Connection,
    ssl_context: Union[None, bool, '_ssl.SSLContext'] = None,
    ssl_handshake_timeout: Optional[float] = None,
    on_open: Optional[List[Callable]] = None,
    on_close: Optional[List[Callable]] = None,
    # below are connection kwargs
    protocol: protocol.Protocol = protocol.Protocol,
    handler_class: Type[handler.Handler] = handler.PBSerialHandler,
    router_class: Type[router.Router] = router.PBRouter,
    middleware_manager: Optional[MiddlewareManager] = None,
    **kwargs,
):
    return await raw_dial_stream(
        address,
        transport_class=transport_class,
        ssl_context=ssl_context,
        ssl_handshake_timeout=ssl_handshake_timeout,
        protocol=protocol,
        handler=handler_class(router_class()),
        **kwargs,
    )


async def serve_stream(
    address: Union[Tuple[str, int], str],
    *,
    transport_class: ConnectionType = Stream | Connection,
    protocol: ProtocolType = protocol.Protocol,
    handler_class: Type[handler.Handler] = handler.PBSerialHandler,
    router_class: Type[router.Router] = router.PBRouter,
    **kwargs,
):
    from pymaid.rpc import serve_stream as raw_serve_stream
    return await raw_serve_stream(
        address=address,
        transport_class=transport_class,
        protocol=protocol,
        handler_class=handler_class,
        router_class=router_class,
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
