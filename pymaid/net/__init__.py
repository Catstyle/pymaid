'''pymaid separate network into two layer

- transport layer
    transport layer concern about how data transmit
    for example: stream for tcp; packet for udp
    and security of transmission: with or without ssl/tls

- protocol layer
    protocol layer concern about how app data format
    it does not care where the data comes from
    stream, packet, file, or pipeline are not different

    you feed it data, and it gives you protocol messages, that's all

    for example: http, protocol buffer, websocket
    and also has the ability to wrap builtin Protocols
    like AppProtocol(PBProtocol) or even AppProtocol(PBProtocol(WSProtocol))
'''

__all__ = ['Protocol', 'Transport', 'Stream', 'Datagram']

import socket
import ssl

from typing import Callable, List, Optional, Tuple, Union


from .channel import ChannelType, StreamChannel
from .raw import sock_connect
from .stream import Stream


async def dial_stream(
    address: Tuple[str, int],
    *,
    transport_class: Stream = Stream,
    ssl_context: Union[None, bool, 'ssl.SSLContext'] = None,
    ssl_handshake_timeout: Optional[float] = None,
    on_open: Optional[List[Callable]] = None,
    on_close: Optional[List[Callable]] = None,
    **kwargs,
):
    '''Create a `Stream` instance that connect to `address`.

    The address parameter can be a string, in that case the stream is
    connect to unix domain sock.

    The address parameter can also be a tuple of string and int, in that case
    the stream is connect to the address and port. If a address
    appears multiple times (possibly indirectly e.g. when hostnames
    resolve to the same IP address), the stream is only connect once to that
    address.

    This method is a coroutine.

    :returns: a `Stream` object.
    '''
    sock = await sock_connect(address)
    stream = transport_class(
        sock,
        initiative=True,
        ssl_context=ssl_context,
        ssl_handshake_timeout=ssl_handshake_timeout,
        on_open=on_open,
        on_close=on_close,
        **kwargs,
    )
    await stream.wait_ready()
    return stream


async def serve_stream(
    address: Union[Tuple[str, int], str],
    *,
    family: socket.AddressFamily = socket.AF_UNSPEC,
    flags: socket.AddressInfo = socket.AI_PASSIVE,
    backlog: int = 128,
    reuse_address: bool = True,
    reuse_port: bool = False,
    ssl_context: Union[None, 'ssl.SSLContext'] = None,
    ssl_handshake_timeout: Optional[float] = None,
    channel_class: ChannelType = StreamChannel,
    transport_class: Stream = Stream,
    start_serving: bool = True,
    **kwargs,
):
    '''Create channel listening on `address`.

    The address parameter can be a string, in that case the TCP Channel is
    bound to unix domain sock.

    The address parameter can also be a tuple of string and int, in that case
    the TCP Channel is bound to the address and port. If a address
    appears multiple times (possibly indirectly e.g. when hostnames
    resolve to the same IP address), the Channel is only bound once to that
    address.

    Return a Channel object which can be used to manage the streams.

    This method is a coroutine.
    '''
    channel = channel_class(
        transport_class=transport_class,
        ssl_context=ssl_context,
        ssl_handshake_timeout=ssl_handshake_timeout,
        **kwargs,
    )
    await channel.listen(
        address,
        family=family,
        flags=flags,
        backlog=backlog,
        reuse_address=reuse_address,
        reuse_port=reuse_port,
    )
    if start_serving:
        channel.start()
    return channel
