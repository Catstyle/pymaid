import os
import socket

import pytest

from pymaid.net.raw import sock_connect, sock_listen
from pymaid.net.raw import HAS_IPv6_FAMILY


@pytest.mark.asyncio
async def test_sock_listen_ipv4():
    sockets = await sock_listen(('localhost', 8999))
    assert sockets
    for sock in sockets:
        assert sock.family == socket.AF_INET
        assert sock.type == socket.SOCK_STREAM
        sock.close()


@pytest.mark.skipif(not HAS_IPv6_FAMILY, reason='does not support ipv6')
@pytest.mark.asyncio
async def test_sock_listen_ipv6():
    sockets = await sock_listen(('::1', 8999))
    assert sockets
    for sock in sockets:
        assert sock.family == socket.AF_INET6
        assert sock.type == socket.SOCK_STREAM
        sock.close()


@pytest.mark.skipif(
    not getattr(socket, 'AF_UNIX', None),
    reason='does not support unix domain sock'
)
@pytest.mark.asyncio
async def test_sock_listen_unix():
    sockets = await sock_listen('/tmp/pymaid_test.sock')
    assert sockets
    for sock in sockets:
        assert sock.family == socket.AF_UNIX
        assert sock.type == socket.SOCK_STREAM
        sock.close()
    os.unlink('/tmp/pymaid_test.sock')


@pytest.mark.asyncio
async def test_sock_connect_ipv4():
    sockets = await sock_listen(('localhost', 8999))
    assert sockets

    sock = await sock_connect(('localhost', 8999))
    assert sock.family == socket.AF_INET
    # localhost resolved to 127.0.0.1
    assert sock.getpeername() == ('127.0.0.1', 8999)

    for listen_sock in sockets:
        peer, addr = listen_sock.accept()
        break
    sock.send(b'from pymaid')
    assert peer.recv(1024) == b'from pymaid'

    peer.close()
    for sock in sockets:
        sock.close()


@pytest.mark.skipif(not HAS_IPv6_FAMILY, reason='does not support ipv6')
@pytest.mark.asyncio
async def test_sock_connect_ipv6():
    sockets = await sock_listen(('::1', 8999))
    assert sockets
    assert len(sockets) == 1

    sock = await sock_connect(('::1', 8999))
    assert sock.family == socket.AF_INET6
    assert sock.getpeername()[:2] == ('::1', 8999)

    for listen_sock in sockets:
        peer, addr = listen_sock.accept()
        break
    sock.send(b'from pymaid')
    assert peer.recv(1024) == b'from pymaid'

    peer.close()
    for sock in sockets:
        sock.close()


@pytest.mark.skipif(
    not getattr(socket, 'AF_UNIX', None),
    reason='does not support unix domain sock'
)
@pytest.mark.asyncio
async def test_sock_connect_unix():
    sockets = await sock_listen('/tmp/pymaid_test_ipv6.sock')
    assert sockets
    assert len(sockets) == 1

    sock = await sock_connect('/tmp/pymaid_test_ipv6.sock')
    assert sock.family == socket.AF_UNIX
    assert sock.getpeername() == '/tmp/pymaid_test_ipv6.sock'

    for listen_sock in sockets:
        peer, addr = listen_sock.accept()
        break
    sock.send(b'from pymaid')
    assert peer.recv(1024) == b'from pymaid'

    peer.close()
    for sock in sockets:
        sock.close()

    os.unlink('/tmp/pymaid_test_ipv6.sock')
