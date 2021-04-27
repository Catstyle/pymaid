import socket

import pytest

from pymaid.core import getaddrinfo


@pytest.mark.asyncio
async def test_getaddrinfo_ipv4():
    infos = await getaddrinfo('localhost', 8888)
    assert infos
    # INET: stream, datagram, raw
    assert infos, infos

    for af, stype in ((socket.AF_INET, socket.SOCK_STREAM),
                      (socket.AF_INET, socket.SOCK_DGRAM)):
        assert any(info[0] == af for info in infos)
        assert any(info[1] == stype for info in infos)
        assert any(info[-1][:2] == ('127.0.0.1', 8888) for info in infos)


@pytest.mark.asyncio
async def test_getaddrinfo_ipv6():
    infos = await getaddrinfo('::1', 8888)
    assert infos
    # INET: stream, datagram, raw
    assert infos, infos

    for af, stype in ((socket.AF_INET6, socket.SOCK_STREAM),
                      (socket.AF_INET6, socket.SOCK_DGRAM)):
        assert any(info[0] == af for info in infos)
        assert any(info[1] == stype for info in infos)
        assert any(info[-1][:2] == ('::1', 8888) for info in infos)
