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
import ssl as _ssl

from typing import Optional, Tuple, Union


from .channel import ChannelType, StreamChannel
from .stream import Stream


async def dial_stream(
    address: Tuple[str, int],
    *,
    channel_class: ChannelType = StreamChannel,
    stream_class: Stream = Stream,
    ssl_context: Union[None, bool, '_ssl.SSLContext'] = None,
    ssl_handshake_timeout: Optional[float] = None,
):
    '''Create channel can connect to `address`.

    The host parameter can be a string, in that case the TCP Channel is
    connect to unix domain sock.

    The host parameter can also be a tuple of string and int, in that case
    the TCP Channel is connect to the host and port. If a host
    appears multiple times (possibly indirectly e.g. when hostnames
    resolve to the same IP address), the Channel is only connect once to that
    host.

    Return a Channel object which can be used to manage the streams.

    This method is a coroutine.
    '''
    return channel_class(
        address=address,
        stream_class=stream_class,
        ssl_context=ssl_context,
        ssl_handshake_timeout=ssl_handshake_timeout,
    )


async def serve_stream(
    address: Union[Tuple[str, int], str],
    *,
    family: socket.AddressFamily = socket.AF_UNSPEC,
    flags: socket.AddressInfo = socket.AI_PASSIVE,
    backlog: int = 128,
    reuse_address: bool = True,
    reuse_port: bool = False,
    ssl_context: Union[None, '_ssl.SSLContext'] = None,
    ssl_handshake_timeout: Optional[float] = None,
    channel_class: ChannelType = StreamChannel,
    stream_class: Stream = Stream,
    start_serving: bool = True,
):
    '''Create channel listening on `address`.

    The host parameter can be a string, in that case the TCP Channel is
    bound to unix domain sock.

    The host parameter can also be a tuple of string and int, in that case
    the TCP Channel is bound to the host and port. If a host
    appears multiple times (possibly indirectly e.g. when hostnames
    resolve to the same IP address), the Channel is only bound once to that
    host.

    Return a Channel object which can be used to manage the streams.

    This method is a coroutine.
    '''
    channel = channel_class(
        stream_class=stream_class,
        ssl_context=ssl_context,
        ssl_handshake_timeout=ssl_handshake_timeout,
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
