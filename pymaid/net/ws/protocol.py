import struct

from itertools import cycle
from typing import Tuple
from urllib.parse import urlparse

from pymaid.conf import settings
from pymaid.net import DataType, Protocol

from .exceptions import ProtocolError, FrameTooLargeException

try:
    from .speedups import apply_mask
    mask_payload = unmask_payload = apply_mask
except ImportError:

    # from_bytes/to_bytes is faster
    # but it is under potential risk of being attack
    # because multiply *mask* is not memory friendly

    # def mask_payload(payload, mask) -> bytes:
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

    def mask_payload(payload: DataType, mask: bytes) -> bytes:
        if len(mask) != 4:
            raise ValueError('mask must be 4 bytes')
        return bytes(b ^ m for b, m in zip(payload, cycle(mask)))

    # it's the same operation
    unmask_payload = mask_payload


__all__ = ['WSProtocol', 'Header', 'mask_payload', 'unmask_payload']

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


class WSProtocol(Protocol):

    HANDSHAKE_REQ = (
        b'GET %s HTTP/1.1\r\n'
        b'Upgrade: websocket\r\n'
        b'Connection: Upgrade\r\n'
        b'Sec-WebSocket-Key: %s\r\n'
        b'Sec-WebSocket-Version: %s\r\n\r\n'
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

    OPCODE_CONTINUATION = 0x00
    OPCODE_TEXT = 0x01
    OPCODE_BINARY = 0x02
    OPCODE_CLOSE = 0x08
    OPCODE_PING = 0x09
    OPCODE_PONG = 0x0a

    def feed_data(self, data: DataType) -> bytes:
        data = memoryview(data)
        messages = []

        used_size = 0
        max_packet = settings.get('MAX_PACKET_LENGTH', ns='pymaid')
        try:
            while 1:
                consumed, meta, payload = self.decode(data, max_packet)
                if not consumed:
                    break
                assert meta
                messages.append((meta, payload))
                used_size += consumed
                data = data[consumed:]
        finally:
            data.release()

        return used_size, messages

    def encode_frame(self, opcode, payload):
        # no mater what opcode, message should be binary type
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        return (
            Header.encode_header(True, opcode, b'', len(payload), 0) + payload
        )

    def encode(self, opcode, payload: DataType) -> bytes:
        '''Send a frame over the websocket with message as its payload.'''
        return self.encode_frame(
            self.OPCODE_BINARY
            if isinstance(payload, bytes)
            else self.OPCODE_TEXT,
            payload,
        )

    def decode(self, data: DataType) -> Tuple[int, DataType]:
        pass

    def handshake_frame(self, resource, key):
        return self.HANDSHAKE_REQ % (resource, key, self.VERSION)


class Header:

    __slots__ = ('fin', 'mask', 'opcode', 'flags', 'length')

    FIN_MASK = 0x80
    OPCODE_MASK = 0x0f
    MASK_MASK = 0x80
    LENGTH_MASK = 0x7f

    RSV0_MASK = 0x40
    RSV1_MASK = 0x20
    RSV2_MASK = 0x10

    # bitwise mask that will determine the reserved bits for a frame header
    HEADER_FLAG_MASK = RSV0_MASK | RSV1_MASK | RSV2_MASK

    def __init__(self, fin=0, opcode=0, flags=0, length=0):
        self.mask = bytearray()
        self.fin = fin
        self.opcode = opcode
        self.flags = flags
        self.length = length

    def __repr__(self):
        return (
            f'<Header fin={self.fin} opcode={self.opcode} '
            f'length={self.length} flags={self.flags} at 0x{id(self):x}>'
        )

    @classmethod
    def decode_header(cls, data: DataType) -> Tuple[int, 'Header']:
        '''Decode a WebSocket header.

        :param data: `DataType`
        :returns: A `Header` instance.
        '''
        nbytes = len(data)
        if nbytes < 2:
            return 0, None

        used_size = 2
        header = data[:2]
        first_byte, second_byte = unpack_header(header)
        header = cls(
            fin=first_byte & cls.FIN_MASK == cls.FIN_MASK,
            opcode=first_byte & cls.OPCODE_MASK,
            flags=first_byte & cls.HEADER_FLAG_MASK,
            length=second_byte & cls.LENGTH_MASK
        )
        has_mask = second_byte & cls.MASK_MASK == cls.MASK_MASK

        if header.opcode > 0x07:
            if not header.fin:
                raise ProtocolError(
                    f'Received fragmented control frame: {data}'
                )
            # Control frames MUST have a payload length of 125 bytes or less
            if header.length > 125:
                raise FrameTooLargeException(
                    f'Control frame cannot be larger than 125 bytes: {data}'
                )

        if header.length == 126:
            # 16 bit length
            if nbytes < (used_size + 2):
                return 0, None
            header.length = unpack_H(data[used_size: used_size + 2])[0]
            used_size += 2
        elif header.length == 127:
            # 64 bit length
            if nbytes < (used_size + 8):
                return 0, None
            header.length = unpack_Q(data[used_size: used_size + 8])[0]
            used_size += 8

        if has_mask:
            if nbytes < (used_size + 4):
                return 0, None
            header.mask = bytearray(data[used_size: used_size + 4])
            used_size += 4
        return used_size, header

    @classmethod
    def encode_header(cls, fin, opcode, mask, length, flags) -> bytes:
        '''Encodes a WebSocket header.

        :param fin: Whether this is the final frame for this opcode.
        :param opcode: The opcode of the payload, see `OPCODE_*`
        :param mask: Whether the payload is masked.
        :param length: The length of the frame.
        :param flags: The RSV* flags.
        :return: A bytestring encoded header.
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
