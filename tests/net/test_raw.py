import os
import socket

import pytest

from pymaid.core import sleep
from pymaid.net.raw import sock_connect, sock_listen
from pymaid.net.raw import HAS_IPv6_FAMILY, HAS_UNIX_FAMILY


@pytest.mark.asyncio
async def test_sock_listen_tcp():
    sockets = await sock_listen('tcp', 'localhost:8990')
    assert sockets
    for sock in sockets:
        assert sock.family in (socket.AF_INET, socket.AF_INET6)
        assert sock.type == socket.SOCK_STREAM
        sock.close()


@pytest.mark.asyncio
async def test_sock_listen_tcp4():
    sockets = await sock_listen('tcp4', 'localhost:8990')
    assert sockets
    for sock in sockets:
        assert sock.family == socket.AF_INET
        assert sock.type == socket.SOCK_STREAM
        sock.close()


@pytest.mark.skipif(not HAS_IPv6_FAMILY, reason='does not support ipv6')
@pytest.mark.asyncio
async def test_sock_listen_tcp6():
    sockets = await sock_listen('tcp6', '[::1]:8991')
    assert sockets
    for sock in sockets:
        assert sock.family == socket.AF_INET6
        assert sock.type == socket.SOCK_STREAM
        sock.close()


@pytest.mark.skipif(
    not HAS_UNIX_FAMILY, reason='does not support unix domain sock'
)
@pytest.mark.asyncio
async def test_sock_listen_unix():
    sockets = await sock_listen('unix', '/tmp/pymaid_test.sock')
    assert sockets
    for sock in sockets:
        assert sock.family == socket.AF_UNIX
        assert sock.type == socket.SOCK_STREAM
        sock.close()
    os.unlink('/tmp/pymaid_test.sock')


@pytest.mark.asyncio
async def test_sock_connect_tcp():
    sockets = await sock_listen('tcp', 'localhost:8992')
    assert sockets

    sock = await sock_connect('tcp', 'localhost:8992')
    assert sock.family in {socket.AF_INET, socket.AF_INET6}
    assert sock.getpeername()[:2] in {('127.0.0.1', 8992), ('::1', 8992)}

    for listen_sock in sockets:
        peer, addr = listen_sock.accept()
        break
    sock.send(b'from pymaid')
    await sleep(0.001)
    assert peer.recv(1024) == b'from pymaid'

    peer.close()
    for sock in sockets:
        sock.close()


@pytest.mark.asyncio
async def test_sock_connect_tcp4():
    sockets = await sock_listen('tcp4', 'localhost:8994')
    assert sockets
    assert len(sockets) == 1

    sock = await sock_connect('tcp4', 'localhost:8994')
    assert sock.family == socket.AF_INET
    assert sock.getpeername()[:2] == ('127.0.0.1', 8994)

    for listen_sock in sockets:
        peer, addr = listen_sock.accept()
        break
    sock.send(b'from pymaid')
    await sleep(0.001)
    assert peer.recv(1024) == b'from pymaid'

    peer.close()
    for sock in sockets:
        sock.close()


@pytest.mark.skipif(not HAS_IPv6_FAMILY, reason='does not support ipv6')
@pytest.mark.asyncio
async def test_sock_connect_tcp6():
    sockets = await sock_listen('tcp6', '[::1]:8993')
    assert sockets
    assert len(sockets) == 1

    sock = await sock_connect('tcp6', '[::1]:8993')
    assert sock.family == socket.AF_INET6
    assert sock.getpeername()[:2] == ('::1', 8993)

    for listen_sock in sockets:
        peer, addr = listen_sock.accept()
        break
    sock.send(b'from pymaid')
    await sleep(0.001)
    assert peer.recv(1024) == b'from pymaid'

    peer.close()
    for sock in sockets:
        sock.close()


@pytest.mark.skipif(
    not HAS_UNIX_FAMILY, reason='does not support unix domain sock'
)
@pytest.mark.asyncio
async def test_sock_connect_unix_stream():
    sockets = await sock_listen('unix', '/tmp/pymaid_test_connect.sock')
    assert sockets
    assert len(sockets) == 1

    sock = await sock_connect('unix', '/tmp/pymaid_test_connect.sock')
    assert sock.family == socket.AF_UNIX
    assert sock.getpeername() == '/tmp/pymaid_test_connect.sock'

    for listen_sock in sockets:
        peer, addr = listen_sock.accept()
        break
    sock.send(b'from pymaid')
    assert peer.recv(1024) == b'from pymaid'

    peer.close()
    for sock in sockets:
        sock.close()

    os.unlink('/tmp/pymaid_test_connect.sock')
