import os
import socket

import pytest

from pymaid.core import sleep
from pymaid.net.raw import HAS_IPv6_FAMILY
from pymaid.net.stream import Stream

from tests.common.models import _TestStream


@pytest.mark.skipif(
    os.name == 'posix', reason='linux system does not support INET4 socketpair'
)
@pytest.mark.asyncio
async def test_stream_ipv4():
    sock1, sock2 = socket.socketpair(socket.AF_INET.value)
    s1, s2 = _TestStream(sock1), _TestStream(sock2)
    await s1.write(b'from pymaid')
    await sleep(0)
    assert s2.received_data == b'from pymaid'
    s1.close()
    s2.close()


@pytest.mark.skipif(
    os.name == 'posix', reason='linux system does not support INET6 socketpair'
)
@pytest.mark.skipif(not HAS_IPv6_FAMILY, reason='does not support ipv6')
@pytest.mark.asyncio
async def test_stream_ipv6():
    sock1, sock2 = socket.socketpair(socket.AF_INET6.value)
    s1, s2 = _TestStream(sock1), _TestStream(sock2)
    await s1.write(b'from pymaid')
    await sleep(0)
    assert s2.received_data == b'from pymaid'
    s1.close()
    s2.close()


@pytest.mark.skipif(
    not getattr(socket, 'AF_UNIX', None),
    reason='does not support unix domain sock'
)
@pytest.mark.asyncio
async def test_stream_unix():
    sock1, sock2 = socket.socketpair(socket.AF_UNIX.value)
    s1, s2 = _TestStream(sock1), _TestStream(sock2)
    await s1.write(b'from pymaid')
    await sleep(0.001)
    assert s2.received_data == b'from pymaid'
    s1.close()
    s2.close()


@pytest.mark.skipif(
    not getattr(socket, 'AF_UNIX', None),
    reason='does not support unix domain sock'
)
@pytest.mark.asyncio
async def test_stream_data_received_overrided():
    sock1, sock2 = socket.socketpair(socket.AF_UNIX.value)

    with pytest.raises(TypeError):
        Stream(sock1)
