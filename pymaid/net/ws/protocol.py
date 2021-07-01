'''
0                   1                   2                   3
0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-------+-+-------------+-------------------------------+
|F|R|R|R| opcode|M| Payload len |    Extended payload length    |
|I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
|N|V|V|V|       |S|             |   (if payload len==126/127)   |
| |1|2|3|       |K|             |                               |
+-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
|     Extended payload length continued, if payload len == 127  |
+ - - - - - - - - - - - - - - - +-------------------------------+
|                               |Masking-key, if MASK set to 1  |
+-------------------------------+-------------------------------+
| Masking-key (continued)       |          Payload Data         |
+-------------------------------- - - - - - - - - - - - - - - - +
:                     Payload Data continued ...                :
+ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
|                     Payload Data continued ...                |
+---------------------------------------------------------------+
'''

import struct

from base64 import b64encode
from enum import IntEnum
from hashlib import sha1
from typing import List, Tuple

from multidict import CIMultiDict
from pymaid.net.protocol import Protocol
from pymaid.types import DataType

from .exceptions import ProtocolError

try:
    from .speedups import apply_mask
except ImportError:

    # https://www.willmcgugan.com/blog/tech/post/speeding-up-websockets-60x/

    _XOR_TABLE = [bytes(a ^ b for a in range(256)) for b in range(256)]

    def apply_mask(payload: DataType, mask: bytes) -> bytes:
        if len(mask) != 4:
            raise ValueError('mask must be 4 bytes')

        a, b, c, d = (_XOR_TABLE[n] for n in mask)
        data_bytes = bytearray(payload)
        data_bytes[::4] = data_bytes[::4].translate(a)
        data_bytes[1::4] = data_bytes[1::4].translate(b)
        data_bytes[2::4] = data_bytes[2::4].translate(c)
        data_bytes[3::4] = data_bytes[3::4].translate(d)
        return bytes(data_bytes)


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


class CloseReason(IntEnum):
    '''RFC 6455, Section 7.4.1 - Defined Status Codes'''

    #: indicates a normal closure, meaning that the purpose for
    #: which the connection was established has been fulfilled.
    NORMAL_CLOSURE = 1000

    #: indicates that an endpoint is 'going away', such as a server
    #: going down or a browser having navigated away from a page.
    GOING_AWAY = 1001

    #: indicates that an endpoint is terminating the connection due
    #: to a protocol error.
    PROTOCOL_ERROR = 1002

    #: indicates that an endpoint is terminating the connection
    #: because it has received a type of data it cannot accept (e.g., an
    #: endpoint that understands only text data MAY send this if it
    #: receives a binary message).
    UNSUPPORTED_DATA = 1003

    #: Reserved.  The specific meaning might be defined in the future.
    # DON'T DEFINE THIS: RESERVED_1004 = 1004

    #: is a reserved value and MUST NOT be set as a status code in a
    #: Close control frame by an endpoint.  It is designated for use in
    #: applications expecting a status code to indicate that no status
    #: code was actually present.
    NO_STATUS_RCVD = 1005

    #: is a reserved value and MUST NOT be set as a status code in a
    #: Close control frame by an endpoint.  It is designated for use in
    #: applications expecting a status code to indicate that the
    #: connection was closed abnormally, e.g., without sending or
    #: receiving a Close control frame.
    ABNORMAL_CLOSURE = 1006

    #: indicates that an endpoint is terminating the connection
    #: because it has received data within a message that was not
    #: consistent with the type of the message (e.g., non-UTF-8 [RFC3629]
    #: data within a text message).
    INVALID_FRAME_PAYLOAD_DATA = 1007

    #: indicates that an endpoint is terminating the connection
    #: because it has received a message that violates its policy.  This
    #: is a generic status code that can be returned when there is no
    #: other more suitable status code (e.g., 1003 or 1009) or if there
    #: is a need to hide specific details about the policy.
    POLICY_VIOLATION = 1008

    #: indicates that an endpoint is terminating the connection
    #: because it has received a message that is too big for it to
    #: process.
    MESSAGE_TOO_BIG = 1009

    #: indicates that an endpoint (client) is terminating the
    #: connection because it has expected the server to negotiate one or
    #: more extension, but the server didn't return them in the response
    #: message of the WebSocket handshake.  The list of extensions that
    #: are needed SHOULD appear in the /reason/ part of the Close frame.
    #: Note that this status code is not used by the server, because it
    #: can fail the WebSocket handshake instead.
    MANDATORY_EXT = 1010

    #: indicates that a server is terminating the connection because
    #: it encountered an unexpected condition that prevented it from
    #: fulfilling the request.
    INTERNAL_ERROR = 1011

    #: is a reserved value and MUST NOT be set as a status code in a
    #: Close control frame by an endpoint.  It is designated for use in
    #: applications expecting a status code to indicate that the
    #: connection was closed due to a failure to perform a TLS handshake
    #: (e.g., the server certificate can't be verified).
    TLS_HANDSHAKE_FAILED = 1015


# RFC 6455, Section 7.4.1 - Defined Status Codes
LOCAL_ONLY_CLOSE_REASONS = {
    CloseReason.NO_STATUS_RCVD,
    CloseReason.ABNORMAL_CLOSURE,
    CloseReason.TLS_HANDSHAKE_FAILED,
}


# RFC 6455, Section 7.4.2 - Status Code Ranges
MIN_CLOSE_REASON = 1000
MIN_PROTOCOL_CLOSE_REASON = 1000
MAX_PROTOCOL_CLOSE_REASON = 2999
MIN_LIBRARY_CLOSE_REASON = 3000
MAX_LIBRARY_CLOSE_REASON = 3999
MIN_PRIVATE_CLOSE_REASON = 4000
MAX_PRIVATE_CLOSE_REASON = 4999
MAX_CLOSE_REASON = 4999


class WSProtocol(Protocol):

    HANDSHAKE_REQ = (
        b'GET %s HTTP/1.1\r\n'
        b'Host: %s\r\n'
        b'Upgrade: WebSocket\r\n'
        b'Connection: Upgrade\r\n'
        b'Sec-WebSocket-Key: %s\r\n'
        b'Sec-WebSocket-Version: %s\r\n'
    )
    HANDSHAKE_RESP = (
        b'HTTP/1.1 101 Switching Protocols\r\n'
        b'Upgrade: WebSocket\r\n'
        b'Connection: Upgrade\r\n'
        b'Sec-WebSocket-Accept: %s\r\n\r\n'
    )

    VERSION = b'13'
    SUPPORTED_VERSIONS = ('13', '8', '7')
    GUID = b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

    MAX_HEADER_SIZE = 4096

    @classmethod
    def feed_data(cls, buf: memoryview) -> Tuple[int, List['Frame']]:
        frames = []
        buf = memoryview(buf)

        total_used = 0
        while 1:
            try:
                used_size, frame = Frame.decode(buf)
            except ProtocolError as ex:
                frames.append(ex)
                break
            if not frame:
                break
            frames.append(frame)
            total_used += used_size
            buf = buf[used_size:]

        return total_used, frames

    @classmethod
    def encode_frame(
        cls,
        opcode: int,
        data: DataType,
        mask: bytes = b''
    ) -> bytes:
        # no mater what opcode, message should be binary type
        if isinstance(data, str):
            data = data.encode('utf-8')
        return Frame.encode(opcode, data, mask)

    @classmethod
    def encode(cls, data: DataType, mask: bytes = b'') -> bytes:
        '''Encode a frame with data as its payload.

        :params data: data to send
        '''
        return cls.encode_frame(
            isinstance(data, str) and Frame.OPCODE_TEXT or Frame.OPCODE_BINARY,
            data,
            mask,
        )

    @classmethod
    def decode(cls, buf: memoryview) -> Tuple[int, 'Frame']:
        '''Decode a `Frame` from the buffer.

        :return: The consumed data length and decoded frame as a tuple.
        '''
        return Frame.decode(buf)

    @classmethod
    def build_request(cls, hostname, resource, key, **headers):
        basic = cls.HANDSHAKE_REQ % (resource, hostname, key, cls.VERSION)
        extra = b''.join(
            b'%s: %s\r\n' % (
                key if isinstance(key, bytes) else key.encode('utf-8'),
                value if isinstance(value, bytes) else value.encode('utf-8')
            )
            for key, value in headers.items()
        )
        return b'%s%s\r\n' % (basic, extra)

    @classmethod
    def build_response(cls, headers: CIMultiDict) -> bytes:
        if ('websocket' != headers.get('Upgrade', '').lower()
                or 'upgrade' != headers.get('Connection', '').lower()):
            raise ProtocolError(
                f'invalid websocket handshake header: {headers}'
            )

        version = headers.get('Sec-WebSocket-Version')
        if version not in cls.SUPPORTED_VERSIONS:
            raise ProtocolError(f'unsupported version={version}')

        sec_key = headers.get('Sec-WebSocket-Key', '')
        if not sec_key:
            raise ProtocolError('missing Sec-WebSocket-Key')

        # TODO: check origin; check host; check headers; check ext

        resp_key = b64encode(sha1(sec_key.encode('utf-8') + cls.GUID).digest())
        return cls.HANDSHAKE_RESP % resp_key

    @classmethod
    def validate_upgrade(cls, headers: CIMultiDict, upgrade_key: bytes):
        if ('websocket' != headers.get('Upgrade', '').lower()
                or 'upgrade' != headers.get('Connection', '').lower()):
            raise ProtocolError(
                f'invalid websocket handshake header: {headers}'
            )

        accept = headers.get('Sec-WebSocket-Accept', '').lower()
        if isinstance(accept, str):
            accept = accept.encode('utf-8')
        value = upgrade_key + cls.GUID
        if b64encode(sha1(value).digest()).strip().lower() != accept:
            raise ProtocolError('invalid accept value')


class Frame:

    __slots__ = (
        'fin', 'opcode', 'flags', 'length', 'mask', 'payload', 'close_reason',
    )

    FIN_MASK = 0x80
    OPCODE_MASK = 0x0f
    MASK_MASK = 0x80
    LENGTH_MASK = 0x7f

    RSV0_MASK = 0x40
    RSV1_MASK = 0x20
    RSV2_MASK = 0x10

    # bitwise mask that will determine the reserved bits for a frame header
    RSV_MASK = RSV0_MASK | RSV1_MASK | RSV2_MASK

    OPCODE_CONTINUATION = 0x00
    OPCODE_TEXT = 0x01
    OPCODE_BINARY = 0x02
    OPCODE_CLOSE = 0x08
    OPCODE_PING = 0x09
    OPCODE_PONG = 0x0a

    def __init__(
        self,
        opcode: int,
        payload: DataType,
        mask: bytes = b'',
        fin: bool = True,
        flags: bytes = b'',
        length: int = 0,
    ):
        if mask:
            payload = apply_mask(payload, mask)
        self.opcode = opcode
        self.payload = payload
        self.mask = mask
        self.fin = fin
        self.flags = flags
        self.length = length or len(payload)
        self.close_reason = None

        self.prepare()

    def prepare(self):
        if self.opcode == self.OPCODE_CLOSE:
            payload = self.payload
            length = self.length
            if not length:
                self.close_reason = CloseReason.NO_STATUS_RCVD
            elif length == 1:
                raise ProtocolError(f'Invalid close frame: {self} {payload}')
            else:
                code = unpack_H(payload[:2])[0]
                if code < MIN_CLOSE_REASON or code > MAX_CLOSE_REASON:
                    raise ProtocolError('invalid close code range')
                try:
                    code = CloseReason(code)
                except ValueError:
                    pass
                if code in LOCAL_ONLY_CLOSE_REASONS:
                    raise ProtocolError('remote CLOSE with local-only reason')
                if (not isinstance(code, CloseReason)
                        and code <= MAX_PROTOCOL_CLOSE_REASON):
                    raise ProtocolError('CLOSE with unknown reserved code')
                try:
                    reason = payload[2:].decode('utf-8')
                except UnicodeDecodeError:
                    raise ProtocolError(
                        'close reason is not valid UTF-8',
                        CloseReason.INVALID_FRAME_PAYLOAD_DATA,
                    )
                if isinstance(code, CloseReason):
                    code.reason = reason
                else:
                    code = (code, reason)
                self.close_reason = code

    def __repr__(self):
        return (
            f'<Frame fin={self.fin} opcode={self.opcode} flags={self.flags} '
            f'length={self.length} mask={self.mask.hex()}>'
        )

    @classmethod
    def encode(
        cls,
        opcode: int,
        data: bytes,
        mask: bytes = b'',
        fin: bool = True,
        flags: bytes = b'',
    ) -> bytes:
        '''Encodes a WebSocket frame.

        :param opcode: The opcode of the payload, see `OPCODE_*`
        :param data: The payload data.
        :param mask: The payload of mask key.
        :param fin: Whether this is the final frame for this opcode.
        :param flags: The RSV* flags.
        :returns: A bytestring encoded frame.
        '''
        first_byte = opcode
        second_byte = 0
        extra = b''

        if fin:
            first_byte |= cls.FIN_MASK
        if flags:
            first_byte |= (flags & cls.RSV_MASK)

        # now deal with length complexities
        length = len(data)
        if length < 126:
            second_byte |= length
        elif length <= 0xffff:
            second_byte |= 126
            extra = pack_H(length)
        elif length <= 0xffffffffffffffff:
            second_byte |= 127
            extra = pack_Q(length)
        else:
            raise ProtocolError(length, CloseReason.MESSAGE_TOO_BIG)

        if mask:
            second_byte |= cls.MASK_MASK
            extra += mask
            data = apply_mask(data, mask)
        return pack_header(first_byte, second_byte) + extra + data

    @classmethod
    def decode(cls, buf: memoryview) -> Tuple[int, 'Frame']:
        '''Decode a WebSocket frame.

        :param data: `DataType`
        :returns: consumed data length and decoded `Frame` instance.
        '''
        if len(buf) < 2:
            return 0, None

        header = buf[:2]
        first_byte, second_byte = unpack_header(header)
        fin = first_byte & cls.FIN_MASK == cls.FIN_MASK
        opcode = first_byte & cls.OPCODE_MASK
        length = second_byte & cls.LENGTH_MASK
        flags = first_byte & cls.RSV_MASK
        has_mask = second_byte & cls.MASK_MASK == cls.MASK_MASK

        if flags:
            raise ProtocolError(f'invalid flags: {flags}')

        if opcode > 0x07:
            if not fin:
                raise ProtocolError('Received fragmented control frame')
            # Control frames MUST have a payload length of 125 bytes or less
            if length > 125:
                raise ProtocolError(
                    f'Control frame cannot be larger than 125 bytes: {length}'
                )

        used_size = 2
        if length == 126:
            # extended payload length: 16 bits
            epl = buf[used_size: used_size + 2]
            if len(epl) < 2:
                return 0, None
            length = unpack_H(epl)[0]
            used_size += 2
        elif length == 127:
            # extended payload length: 64 bits
            epl = buf[used_size: used_size + 8]
            if len(epl) < 8:
                return 0, None
            length = unpack_Q(epl)[0]
            used_size += 8

        mask = b''
        if has_mask:
            mask = buf[used_size: used_size + 4].tobytes()
            if len(mask) < 4:
                return 0, None
            used_size += 4

        payload = buf[used_size: used_size + length]
        if len(payload) < length:
            return 0, None
        used_size += length

        return used_size, cls(
            opcode=opcode,
            payload=payload,
            mask=mask,
            fin=fin,
            flags=flags,
            length=length,
        )
