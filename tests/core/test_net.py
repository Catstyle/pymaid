import socket

import pytest

from pymaid.core import getaddrinfo


@pytest.mark.asyncio
async def test_getaddrinfo_ipv4():
    infos = await getaddrinfo('localhost', 8888)
    assert infos
    # INET: stream, datagram, raw
    assert len(infos) == 3, infos

    info = infos[0]
    assert info[0] == socket.AF_INET
    assert info[1] == socket.SOCK_STREAM
    assert info[-1] == ('127.0.0.1', 8888)

    info = infos[1]
    assert info[0] == socket.AF_INET
    assert info[1] == socket.SOCK_DGRAM
    assert info[-1] == ('127.0.0.1', 8888)

    info = infos[2]
    assert info[0] == socket.AF_INET
    assert info[1] == socket.SOCK_RAW
    assert info[-1] == ('127.0.0.1', 8888)


@pytest.mark.asyncio
async def test_getaddrinfo_ipv6():
    infos = await getaddrinfo('::1', 8888)
    assert infos
    # INET: stream, datagram, raw
    assert len(infos) == 3, infos

    info = infos[0]
    assert info[0] == socket.AF_INET6
    assert info[1] == socket.SOCK_STREAM
    assert info[-1][:2] == ('::1', 8888)

    info = infos[1]
    assert info[0] == socket.AF_INET6
    assert info[1] == socket.SOCK_DGRAM
    assert info[-1][:2] == ('::1', 8888)

    info = infos[2]
    assert info[0] == socket.AF_INET6
    assert info[1] == socket.SOCK_RAW
    assert info[-1][:2] == ('::1', 8888)
