import os

from base64 import b64encode
from hashlib import sha1

from multidict import CIMultiDict
from pymaid.net.ws.protocol import WSProtocol

from tests.common import ws_data


def test_build_request_handshake():
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


def test_build_request_handshake_error():
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


def test_build_response_handshake():
    key = b64encode(os.urandom(16)).strip()
    resp = WSProtocol.build_response(CIMultiDict({
        'Upgrade': 'WebSocket',
        'Connection': 'Upgrade',
        'Sec-WebSocket-Key': key.decode('utf-8'),
        'Sec-WebSocket-Version': '13',
    }))
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


def test_binary_data_frame():
    consumed, frames = WSProtocol.feed_data(ws_data.BINARY_DATA_1024_MASKED)
    assert consumed == len(ws_data.BINARY_DATA_1024_MASKED)
    assert len(frames) == 1

    frame = frames[0]
    assert frame.opcode == frame.OPCODE_BINARY
    assert frame.fin
    assert not frame.flags
    assert frame.mask == b'\xc3\xa8u`'
    assert frame.length == 1024
    assert frame.payload == b'a' * 1024

    consumed, frames = WSProtocol.feed_data(ws_data.BINARY_DATA_1024_UNMASKED)
    assert consumed == len(ws_data.BINARY_DATA_1024_UNMASKED)
    assert len(frames) == 1

    frame = frames[0]
    assert frame.opcode == frame.OPCODE_BINARY
    assert frame.fin
    assert not frame.flags
    assert frame.mask == b''
    assert frame.length == 1024
    assert frame.payload == b'a' * 1024


def test_text_data_frame():
    consumed, frames = WSProtocol.feed_data(ws_data.TEXT_DATA_1024_MASKED)
    assert consumed == len(ws_data.TEXT_DATA_1024_MASKED)
    assert len(frames) == 1

    frame = frames[0]
    assert frame.opcode == frame.OPCODE_TEXT
    assert frame.fin
    assert not frame.flags
    assert frame.mask == b'\xc3\xa8u`'
    assert frame.length == 1024
    assert frame.payload == b'a' * 1024

    consumed, frames = WSProtocol.feed_data(ws_data.TEXT_DATA_1024_UNMASKED)
    assert consumed == len(ws_data.TEXT_DATA_1024_UNMASKED)
    assert len(frames) == 1

    frame = frames[0]
    assert frame.opcode == frame.OPCODE_TEXT
    assert frame.fin
    assert not frame.flags
    assert frame.mask == b''
    assert frame.length == 1024
    assert frame.payload == b'a' * 1024
