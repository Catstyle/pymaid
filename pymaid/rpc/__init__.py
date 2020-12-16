import ssl as _ssl
from typing import Optional, Sequence, Tuple, Type, Union

from pymaid.ext.middleware import MiddlewareManager
from pymaid.net import ProtocolType, Stream

from . import channel
from . import handler
from . import pb
from . import router

from .types import ServiceType

__all__ = ('channel', 'pb')


async def serve_stream(
    address: Union[Tuple[str, int], str],
    *,
    name: str = 'StreamChannel',
    middleware_manager: Optional[MiddlewareManager] = None,
    close_conn_onerror: bool = True,
    connection_class: channel.ConnectionType = channel.Connection,
    protocol_class: Type[ProtocolType] = Stream,
    handler_class: Optional[Type[handler.Handler]] = handler.SerialHandler,
    services: Optional[Sequence[ServiceType]] = None,
    router: Optional[router.Router] = None,
    ssl: Union[None, bool, '_ssl.SSLContext'] = None,
):
    assert services or router, 'should provide services or router'
    ch = channel.create_stream_channel(
        address,
        name=name,
        middleware_manager=middleware_manager,
        close_conn_onerror=close_conn_onerror,
        protocol_class=protocol_class,
        handler_class=handler_class,
    )
    if services:
        ch.router.include_services(services)
    if router:
        ch.router.include_router(router)
    await ch.listen(address, ssl=ssl)
    await ch.start()
    async with ch:
        await ch.serve_forever()
