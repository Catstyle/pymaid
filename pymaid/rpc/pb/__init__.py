import ssl as _ssl
from typing import Optional, Sequence, Tuple, Type, Union

from pymaid.ext.middleware import MiddlewareManager
from pymaid.rpc.channel import ConnectionType
from pymaid.rpc.router import ServiceRepository

from . import channel
from . import connection
from . import handler
from . import protocol

__all__ = ('channel', 'connection', 'handler', 'protocol')


def create_channel(
    address: Union[Tuple[str, int], str],
    *,
    name: str = 'PBChannel',
    middleware_manager: Optional[MiddlewareManager] = None,
    close_conn_onerror: bool = True,
    connection_class: ConnectionType = connection.Connection,
    protocol_class: Type[protocol.Protocol] = protocol.Protocol,
    handler_class: Type[handler.Handler] = handler.SerialHandler,
) -> channel.ChannelType:
    if isinstance(address, str):
        channel_cls = channel.UnixStreamChannel
    else:
        channel_cls = channel.StreamChannel
    return channel_cls(
        name=name,
        middleware_manager=middleware_manager,
        close_conn_onerror=close_conn_onerror,
        protocol_class=protocol_class,
        handler_class=handler_class,
    )


async def serve(
    address: Union[Tuple[str, int], str],
    *,
    name: str = 'PBChannel',
    middleware_manager: Optional[MiddlewareManager] = None,
    close_conn_onerror: bool = True,
    connection_class: ConnectionType = connection.Connection,
    protocol_class: Type[protocol.Protocol] = protocol.Protocol,
    handler_class: Type[handler.Handler] = handler.SerialHandler,
    services: Optional[Sequence[channel.GeneratedServiceType]] = None,
    repository: Optional[ServiceRepository] = None,
    ssl: Union[None, bool, '_ssl.SSLContext'] = None,
):
    assert services or repository, 'should provide services or repository'
    ch = create_channel(
        address,
        name=name,
        middleware_manager=middleware_manager,
        close_conn_onerror=close_conn_onerror,
        protocol_class=protocol_class,
        handler_class=handler_class,
    )
    ch.add_services(services=services, repository=repository)
    await ch.listen(address, ssl=ssl)
    await ch.start()
    async with ch:
        await ch.serve_forever()
