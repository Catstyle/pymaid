import socket

import pytest

from pymaid.net.raw import getaddrinfo, HAS_IPv6_FAMILY, HAS_UNIX_FAMILY
from pymaid.net.raw import STREAM_OPTS, DATAGRAM_OPTS, NET_OPTS


@pytest.mark.asyncio
async def test_getaddrinfo_tcp():
    infos = await getaddrinfo('localhost:8888', *STREAM_OPTS['tcp'])
    assert infos, infos

    families = [socket.AF_INET]
    if HAS_IPv6_FAMILY:
        families.append(socket.AF_INET6)
    for info in infos:
        assert info[0] in families
        assert info[1] == socket.SOCK_STREAM
        assert info[-1][:2] in (('127.0.0.1', 8888), ('::1', 8888))


@pytest.mark.asyncio
async def test_getaddrinfo_tcp4():
    infos = await getaddrinfo('localhost:8888', *STREAM_OPTS['tcp4'])
    assert infos, infos

    for info in infos:
        assert info[0] == socket.AF_INET
        assert info[1] == socket.SOCK_STREAM
        assert info[-1][:2] == ('127.0.0.1', 8888)


@pytest.mark.skipif(not HAS_IPv6_FAMILY, reason='does not support ipv6')
@pytest.mark.asyncio
async def test_getaddrinfo_tcp6():
    infos = await getaddrinfo('[::1]:8888', *STREAM_OPTS['tcp6'])
    assert infos, infos

    for info in infos:
        assert info[0] == socket.AF_INET6
        assert info[1] == socket.SOCK_STREAM
        assert info[-1][:2] == ('::1', 8888)


@pytest.mark.asyncio
async def test_getaddrinfo_udp():
    infos = await getaddrinfo('localhost:8888', *DATAGRAM_OPTS['udp'])
    assert infos, infos

    families = [socket.AF_INET]
    if HAS_IPv6_FAMILY:
        families.append(socket.AF_INET6)
    for info in infos:
        assert info[0] in families
        assert info[1] == socket.SOCK_DGRAM
        assert info[-1][:2] in (('127.0.0.1', 8888), ('::1', 8888))


@pytest.mark.asyncio
async def test_getaddrinfo_udp4():
    infos = await getaddrinfo('localhost:8888', *DATAGRAM_OPTS['udp4'])
    assert infos, infos

    for info in infos:
        assert info[0] == socket.AF_INET
        assert info[1] == socket.SOCK_DGRAM
        assert info[-1][:2] == ('127.0.0.1', 8888)


@pytest.mark.skipif(not HAS_IPv6_FAMILY, reason='does not support ipv6')
@pytest.mark.asyncio
async def test_getaddrinfo_udp6():
    infos = await getaddrinfo('[::1]:8888', *DATAGRAM_OPTS['udp6'])
    assert infos, infos

    for info in infos:
        assert info[0] == socket.AF_INET6
        assert info[1] == socket.SOCK_DGRAM
        assert info[-1][:2] == ('::1', 8888)


@pytest.mark.skipif(
    not HAS_UNIX_FAMILY, reason='does not support unix domain sock',
)
@pytest.mark.asyncio
async def test_getaddrinfo_unix():
    infos = await getaddrinfo('/localhost:8888', *NET_OPTS['unix'])
    assert infos, infos

    for info in infos:
        assert info[0] == socket.AF_UNIX
        assert info[1] in (socket.SOCK_STREAM, socket.SOCK_DGRAM)
        assert info[-1] == '/localhost:8888'


@pytest.mark.skipif(
    not HAS_UNIX_FAMILY, reason='does not support unix domain sock',
)
@pytest.mark.asyncio
async def test_getaddrinfo_unix_stream():
    infos = await getaddrinfo('/localhost:8888', *STREAM_OPTS['unix'])
    assert infos, infos

    for info in infos:
        assert info[0] == socket.AF_UNIX
        assert info[1] == socket.SOCK_STREAM
        assert info[-1] == '/localhost:8888'


@pytest.mark.skipif(
    not HAS_UNIX_FAMILY, reason='does not support unix domain sock',
)
@pytest.mark.asyncio
async def test_getaddrinfo_unix_datagram():
    infos = await getaddrinfo('/localhost:8888', *DATAGRAM_OPTS['unix'])
    assert infos, infos

    for info in infos:
        assert info[0] == socket.AF_UNIX
        assert info[1] == socket.SOCK_DGRAM
        assert info[-1] == '/localhost:8888'


@pytest.mark.asyncio
async def test_getaddrinfo_any():
    infos = await getaddrinfo('localhost:8888', *NET_OPTS['any'])
    assert infos, infos

    for info in infos:
        assert info[0] in (socket.AF_INET, socket.AF_INET6)
        assert info[1] in (
            socket.SOCK_STREAM, socket.SOCK_DGRAM, socket.SOCK_RAW
        )
        assert info[-1][:2] in (('127.0.0.1', 8888), ('::1', 8888))


@pytest.mark.skipif(
    not HAS_UNIX_FAMILY, reason='does not support unix domain sock',
)
@pytest.mark.asyncio
async def test_getaddrinfo_any_unix():
    infos = await getaddrinfo('/localhost:8888', *NET_OPTS['any'])
    assert infos, infos

    for info in infos:
        assert info[0] == socket.AF_UNIX, infos
        assert info[1] in (socket.SOCK_STREAM, socket.SOCK_DGRAM), infos
        assert info[-1] == '/localhost:8888', infos
