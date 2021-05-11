import os

from base64 import b64encode
from hashlib import sha1

import pytest

from pymaid.net.ws.protocol import WSProtocol


@pytest.mark.asyncio
async def test_build_request_handshake():
    key = b64encode(os.urandom(16)).strip()
    req = WSProtocol.build_request(b'pymaid.test', b'/', key)
    assert req == (
        b'GET / HTTP/1.1\r\n'
        b'Host: pymaid.test\r\n'
        b'Upgrade: WebSocket\r\n'
        b'Connection: Upgrade\r\n'
        b'Sec-WebSocket-Key: %s\r\n'
        b'Sec-WebSocket-Version: 13\r\n\r\n'
    ) % (key,)

    req = WSProtocol.build_request(
        b'pymaid.test', b'/', key, **{'Origin': 'pymaid.test'}
    )
    assert req == (
        b'GET / HTTP/1.1\r\n'
        b'Host: pymaid.test\r\n'
        b'Upgrade: WebSocket\r\n'
        b'Connection: Upgrade\r\n'
        b'Sec-WebSocket-Key: %s\r\n'
        b'Sec-WebSocket-Version: 13\r\n'
        b'Origin: pymaid.test\r\n\r\n'
    ) % (key,)


@pytest.mark.asyncio
async def test_build_request_handshake_error():
    key = b64encode(os.urandom(16)).strip()
    req = WSProtocol.build_request(b'', b'/', key)
    assert req == (
        b'GET / HTTP/1.1\r\n'
        b'Host: \r\n'
        b'Upgrade: WebSocket\r\n'
        b'Connection: Upgrade\r\n'
        b'Sec-WebSocket-Key: %s\r\n'
        b'Sec-WebSocket-Version: 13\r\n\r\n'
    ) % (key,)

    req = WSProtocol.build_request(
        b'', b'/', key, **{'Origin': 'pymaid.test'}
    )
    assert req == (
        b'GET / HTTP/1.1\r\n'
        b'Host: \r\n'
        b'Upgrade: WebSocket\r\n'
        b'Connection: Upgrade\r\n'
        b'Sec-WebSocket-Key: %s\r\n'
        b'Sec-WebSocket-Version: 13\r\n'
        b'Origin: pymaid.test\r\n\r\n'
    ) % (key,)


@pytest.mark.asyncio
async def test_build_response_handshake():
    key = b64encode(os.urandom(16)).strip()
    resp = WSProtocol.build_response({
        b'Upgrade': b'WebSocket',
        b'Connection': b'Upgrade',
        b'Sec-WebSocket-Key': key,
        b'Sec-WebSocket-Version': b'13',
    })
    resp_key = b64encode(sha1(key + WSProtocol.GUID).digest())
    assert resp == (
        b'HTTP/1.1 101 Switching Protocols\r\n'
        b'Upgrade: WebSocket\r\n'
        b'Connection: Upgrade\r\n'
        b'Sec-WebSocket-Accept: %s\r\n\r\n'
    ) % (resp_key,)

    req = WSProtocol.build_request(
        b'pymaid.test', b'/', key, **{'Origin': 'pymaid.test'}
    )
    assert req == (
        b'GET / HTTP/1.1\r\n'
        b'Host: pymaid.test\r\n'
        b'Upgrade: WebSocket\r\n'
        b'Connection: Upgrade\r\n'
        b'Sec-WebSocket-Key: %s\r\n'
        b'Sec-WebSocket-Version: 13\r\n'
        b'Origin: pymaid.test\r\n\r\n'
    ) % (key,)
