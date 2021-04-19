import struct

from base64 import b64encode
from hashlib import sha1
from io import BytesIO
from itertools import cycle
from typing import List, IO, Tuple
from urllib.parse import urlparse

from pymaid.net.protocol import Protocol
from pymaid.types import DataType

from .exceptions import ProtocolError, FrameTooLargeException

try:
    from .speedups import apply_mask
except ImportError:

    # from_bytes/to_bytes is faster
    # but it is under potential risk of being attack
    # because multiply *mask* is not memory friendly

    # def apply_mask(payload, mask) -> bytes:
    #     p_size = len(payload)
    #     m_size = len(mask)
    #     if p_size > m_size:
    #         q = p_size // m_size
    #         r = p_size % m_size
    #         mask = mask * q + mask[:r]
    #     elif p_size < m_size:
    #         mask = mask[:p_size]

    #     return (
    #         int.from_bytes(payload, 'little') ^ int.from_bytes(mask, 'little')  # noqa
    #     ).to_bytes(p_size, 'little')

    def apply_mask(payload: DataType, mask: bytes) -> bytes:
        if len(mask) != 4:
            raise ValueError('mask must be 4 bytes')
        return bytes(b ^ m for b, m in zip(payload, cycle(mask)))


__all__ = ['WSProtocol', 'Frame', 'apply_mask']

st = struct.Struct('!BB')
pack_header = st.pack
unpack_header = st.unpack

st_H = struct.Struct('!H')
pack_H = st_H.pack
unpack_H = st_H.unpack

st_Q = struct.Struct('!Q')
pack_Q = st_Q.pack
unpack_Q = st_Q.unpack


def parse_url(url: str):
    if ':' not in url:
        raise ValueError('url is invalid')

    scheme, url = url.split(':', 1)

    is_secure = False
    port = 0
    if scheme == 'ws':
        if not port:
            port = 80
    elif scheme == 'wss':
        is_secure = True
        if not port:
            port = 443
    else:
        raise ValueError(f'scheme {scheme} is invalid')

    parsed = urlparse(url, scheme='ws')
    if parsed.hostname:
        hostname = parsed.hostname
    else:
        raise ValueError('hostname is invalid')

    if parsed.port:
        port = parsed.port

    if parsed.path:
        resource = parsed.path
    else:
        resource = '/'

    if parsed.query:
        resource += '?' + parsed.query

    return hostname, port, resource, is_secure


def parse_request(buf: IO):
    pass


def parse_response(buf: IO):
    pass


def parse_headers(buf: IO):
    headers = {}
    readline = buf.readline
    while 1:
        line = readline(1024)
        if line == b'\r\n':
            break
        line = line.strip()
        if not line:
            # empty string, not enough data
            headers = {}
            break
        key, value = line.split(b':', 1)
        headers[key] = value.strip()
    return headers


class WSProtocol(Protocol):

    HANDSHAKE_REQ = (
        b'GET %s HTTP/1.1\r\n'
        b'Upgrade: websocket\r\n'
        b'Connection: Upgrade\r\n'
        b'Sec-WebSocket-Key: %s\r\n'
        b'Sec-WebSocket-Version: %s\r\n'
    )
    HANDSHAKE_RESP = (
        b'HTTP/1.1 101 Switching Protocols\r\n'
        b'Upgrade: websocket\r\n'
        b'Connection: Upgrade\r\n'
        b'Sec-WebSocket-Accept: %s\r\n\r\n'
    )

    VERSION = b'13'
    SUPPORTED_VERSIONS = (b'13', b'8', b'7')
    GUID = b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

    MAX_HEADER_SIZE = 4096

    @classmethod
    def feed_data(cls, buf: BytesIO) -> Tuple[int, List['Frame']]:
        frames = []

        total_used = 0
        while 1:
            used_size, frame = cls.decode(buf)
            if not frame:
                break
            frames.append(frame)
            total_used += used_size

        return total_used, frames

    @classmethod
    def encode_frame(cls, opcode: int, data: DataType) -> bytes:
        # no mater what opcode, message should be binary type
        if isinstance(data, str):
            data = data.encode('utf-8')
        return Frame.encode(True, opcode, b'', len(data), 0) + data

    @classmethod
    def encode(cls, data: DataType) -> bytes:
        '''Encode a frame with data as its payload.

        :params data: data to send
        '''
        return cls.encode_frame(
            isinstance(data, str) and Frame.OPCODE_TEXT or Frame.OPCODE_BINARY,
            data,
        )

    @classmethod
    def decode(cls, buf: IO) -> Tuple[int, 'Frame']:
        '''Decode a `Frame` from the buffer.

        :return: The frame and payload as a tuple.
        '''
        used_size, frame = Frame.decode(buf)
        if not frame:
            return 0, None

        if frame.flags:
            raise ProtocolError(f'invalid flags: {frame.flags}')

        return used_size, frame

    @classmethod
    def build_request(cls, resource, key, **headers):
        basic = cls.HANDSHAKE_REQ % (resource, key, cls.VERSION)
        extra = b''.join(
            b'%s: %s\r\n' % (
                key if isinstance(key, bytes) else key.encode('utf-8'),
                value if isinstance(value, bytes) else value.encode('utf-8')
            )
            for key, value in headers.items()
        )
        return b'%s%s\r\n' % (basic, extra)

    @classmethod
    def parse_request(cls, buf: IO) -> bytes:
        '''Parse a upgrade request from the buffer.

        :params readline: `Callable` that returns a `CRLF` terminated line
        :returns: A upgrade response bytes body
        '''
        line = buf.readline()
        if len(line) >= cls.MAX_HEADER_SIZE:
            raise ProtocolError(
                f'header size too large, max={cls.MAX_HEADER_SIZE}'
            )
        assert line, 'should not reach here when read_buffer is empty'

        datas = line.split()
        if len(datas) != 3:
            raise ProtocolError(f'invalid request status line: {line}')
        method, path, version = datas
        if method != b'GET' or version != b'HTTP/1.1':
            raise ProtocolError(
                f'websocket requried GET HTTP/1.1, got `{line}`'
            )

        headers = parse_headers(buf)
        if not headers:
            return
        return cls.build_response(headers)

    @classmethod
    def build_response(cls, headers: dict) -> bytes:
        if (b'websocket' != headers.get(b'Upgrade')
                or b'Upgrade' != headers.get(b'Connection')):
            raise ProtocolError('invalid websocket handshake header')

        version = headers.get(b'Sec-WebSocket-Version')
        if version not in cls.SUPPORTED_VERSIONS:
            raise ProtocolError(f'unsupported {version=}')

        if not (sec_key := headers.get(b'Sec-WebSocket-Key', b'')):
            raise ProtocolError('missing Sec-WebSocket-Key')

        resp_key = b64encode(sha1(sec_key + cls.GUID).digest())
        return cls.HANDSHAKE_RESP % resp_key

    @classmethod
    def parse_response(cls, buf: IO, secret_key: bytes):
        line = buf.readline(1024)
        assert line, 'should not reach here when read_buffer is empty'

        status = line.split(b' ', 2)
        if len(status) != 3:
            raise ProtocolError(f'invalid response status line: {line}')
        status = int(status[1])
        if status != 101:
            raise ProtocolError(f'handshake failed with status: {status}')

        headers = parse_headers(buf)
        if not headers:
            return False
        cls.validate_upgrade(headers, secret_key)
        return True

    @classmethod
    def validate_upgrade(cls, headers: dict, upgrade_key: bytes):
        if (b'websocket' != headers.get(b'Upgrade')
                or b'Upgrade' != headers.get(b'Connection')):
            raise ProtocolError('invalid websocket handshake header')

        accept = headers.get(b'Sec-WebSocket-Accept', '').lower()
        if isinstance(accept, str):
            accept = accept.encode('utf-8')
        value = upgrade_key + cls.GUID
        if b64encode(sha1(value).digest()).strip().lower() != accept:
            raise ProtocolError('invalid accept value')


class Frame:

    __slots__ = ('fin', 'mask', 'opcode', 'flags', 'length', 'payload')

    FIN_MASK = 0x80
    OPCODE_MASK = 0x0f
    MASK_MASK = 0x80
    LENGTH_MASK = 0x7f

    RSV0_MASK = 0x40
    RSV1_MASK = 0x20
    RSV2_MASK = 0x10

    # bitwise mask that will determine the reserved bits for a frame header
    HEADER_FLAG_MASK = RSV0_MASK | RSV1_MASK | RSV2_MASK

    OPCODE_CONTINUATION = 0x00
    OPCODE_TEXT = 0x01
    OPCODE_BINARY = 0x02
    OPCODE_CLOSE = 0x08
    OPCODE_PING = 0x09
    OPCODE_PONG = 0x0a

    def __init__(self, fin=0, opcode=0, flags=0, length=0):
        self.mask = bytearray()
        self.fin = fin
        self.opcode = opcode
        self.flags = flags
        self.length = length
        self.payload = b''

    def __repr__(self):
        return (
            f'<Frame fin={self.fin} opcode={self.opcode} '
            f'length={self.length} flags={self.flags} at 0x{id(self):x}>'
        )

    @classmethod
    def decode(cls, buf: IO) -> Tuple[int, 'Frame']:
        '''Decode a WebSocket frame.

        :param data: `DataType`
        :returns: A `Frame` instance.
        '''
        if len((header := buf.read(2))) < 2:
            return 0, None

        first_byte, second_byte = unpack_header(header)
        frame = cls(
            fin=first_byte & cls.FIN_MASK == cls.FIN_MASK,
            opcode=first_byte & cls.OPCODE_MASK,
            flags=first_byte & cls.HEADER_FLAG_MASK,
            length=second_byte & cls.LENGTH_MASK
        )
        has_mask = second_byte & cls.MASK_MASK == cls.MASK_MASK

        if frame.opcode > 0x07:
            if not frame.fin:
                raise ProtocolError('Received fragmented control frame')
            # Control frames MUST have a payload length of 125 bytes or less
            if frame.length > 125:
                raise FrameTooLargeException(
                    f'Control frame cannot be larger than 125 bytes: '
                    f'{frame.length}'
                )

        used_size = 2
        if frame.length == 126:
            # extended payload length: 16 bits
            if len((epl := buf.read(2))) < 2:
                return 0, None
            frame.length = unpack_H(epl)[0]
            used_size += 2
        elif frame.length == 127:
            # extended payload length: 64 bits
            if len((epl := buf.read(8))) < 8:
                return 0, None
            frame.length = unpack_Q(epl)[0]
            used_size += 8

        if has_mask:
            if len((mask_key := buf.read(4))) < 4:
                return 0, None
            frame.mask = bytearray(mask_key)
            used_size += 4

        payload = buf.read(frame.length)
        if len(payload) < frame.length:
            return 0, None
            # raise ProtocolError('Unexpected EOF reading frame payload')
        used_size += frame.length

        if frame.mask:
            payload = apply_mask(payload, frame.mask)

        frame.payload = payload

        return used_size, frame

    @classmethod
    def encode(cls, fin, opcode, mask, length, flags) -> bytes:
        '''Encodes a WebSocket frame.

        :param fin: Whether this is the final frame for this opcode.
        :param opcode: The opcode of the payload, see `OPCODE_*`
        :param mask: Whether the payload is masked.
        :param length: The length of the frame.
        :param flags: The RSV* flags.
        :return: A bytestring encoded frame.
        '''
        first_byte = opcode
        second_byte = 0
        extra = b''

        if fin:
            first_byte |= cls.FIN_MASK
        if flags & cls.RSV0_MASK:
            first_byte |= cls.RSV0_MASK
        if flags & cls.RSV1_MASK:
            first_byte |= cls.RSV1_MASK
        if flags & cls.RSV2_MASK:
            first_byte |= cls.RSV2_MASK

        # now deal with length complexities
        if length < 126:
            second_byte += length
        elif length <= 0xffff:
            second_byte += 126
            extra = pack_H(length)
        elif length <= 0xffffffffffffffff:
            second_byte += 127
            extra = pack_Q(length)
        else:
            raise FrameTooLargeException(length)

        if mask:
            second_byte |= cls.MASK_MASK
            extra += mask
        return pack_header(first_byte, second_byte) + extra
