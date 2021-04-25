import os
import socket

import pytest

from pymaid.core import sleep
from pymaid.net import dial_stream, serve_stream
from pymaid.net.raw import HAS_IPv6_FAMILY

from tests.common.models import _TestStreamChannel, _TestStream


@pytest.mark.asyncio
async def test_stream_channel_ipv4():
    server = await serve_stream(
        ('localhost', 8999),
        channel_class=_TestStreamChannel,
        transport_class=_TestStream,
        start_serving=True,
    )
    assert server

    stream = await dial_stream(
        ('localhost', 8999),
        transport_class=_TestStream,
    )
    assert stream.family == socket.AF_INET
    # localhost resolved to 127.0.0.1
    assert stream.peername == ('127.0.0.1', 8999)

    await stream.write(b'from pymaid')
    # skip one step to let data_received run
    await sleep(0)

    assert server.connected_stream
    assert server.connected_stream.received_data == b'from pymaid'

    stream.close()
    server.connected_stream.close()
    server.close()


@pytest.mark.skipif(not HAS_IPv6_FAMILY, reason='does not support ipv6')
@pytest.mark.asyncio
async def test_stream_channel_ipv6():
    server = await serve_stream(
        ('::1', 8999),
        channel_class=_TestStreamChannel,
        transport_class=_TestStream,
        start_serving=True,
    )
    assert server

    stream = await dial_stream(
        ('::1', 8999),
        transport_class=_TestStream,
    )
    assert stream.family == socket.AF_INET6
    assert stream.peername[:2] == ('::1', 8999)

    await stream.write(b'from pymaid')
    # skip one step to let data_received run
    await sleep(0)

    assert server.connected_stream
    assert server.connected_stream.received_data == b'from pymaid'

    stream.close()
    server.connected_stream.close()
    server.close()


@pytest.mark.skipif(
    not getattr(socket, 'AF_UNIX', None),
    reason='does not support unix domain sock'
)
@pytest.mark.asyncio
async def test_stream_channel_unix():
    server = await serve_stream(
        '/tmp/pymaid_test_ipv6.sock',
        channel_class=_TestStreamChannel,
        transport_class=_TestStream,
        start_serving=True,
    )
    assert server

    stream = await dial_stream(
        '/tmp/pymaid_test_ipv6.sock',
        transport_class=_TestStream,
    )
    assert stream.family == socket.AF_UNIX
    assert stream.peername == '/tmp/pymaid_test_ipv6.sock'

    # remove below one sleep will fail
    # seems like connection_made/data_received only run one
    # but why INET/INET6 does not has this issue?
    await sleep(0)
    await stream.write(b'from pymaid')
    # skip one step to let data_received run
    await sleep(0)

    assert server.connected_stream
    assert server.connected_stream.received_data == b'from pymaid'

    stream.close()
    server.connected_stream.close()
    server.close()
    os.unlink('/tmp/pymaid_test_ipv6.sock')
