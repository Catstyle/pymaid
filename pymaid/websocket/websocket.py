import os
import struct
import base64
from functools import partial

from io import BytesIO
from hashlib import sha1
from socket import AF_INET
from socket import error as socket_error

from six import text_type, string_types
from six.moves.urllib.parse import urlparse

from gevent.socket import socket as realsocket
from gevent.event import Event

from pymaid.connection import Connection
from pymaid.conf import settings
from pymaid.utils.logger import pymaid_logger_wrapper

from .exceptions import ProtocolError, WebSocketError, FrameTooLargeException
from .utf8validator import Utf8Validator

__all__ = ['WebSocket']


def parse_url(url):
    if ":" not in url:
        raise ValueError("url is invalid")

    scheme, url = url.split(":", 1)

    is_secure = False
    port = 0
    if scheme == "ws":
        if not port:
            port = 80
    elif scheme == "wss":
        is_secure = True
        if not port:
            port = 443
    else:
        raise ValueError("scheme %s is invalid" % scheme)

    parsed = urlparse(url, scheme="ws")
    if parsed.hostname:
        hostname = parsed.hostname
    else:
        raise ValueError("hostname is invalid")

    if parsed.port:
        port = parsed.port

    if parsed.path:
        resource = parsed.path
    else:
        resource = "/"

    if parsed.query:
        resource += "?" + parsed.query

    return hostname, port, resource, is_secure


@pymaid_logger_wrapper
class WebSocket(Connection):

    VERSION = 13
    SUPPORTED_VERSIONS = ('13', '8', '7')
    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    OPCODE_CONTINUATION = 0x00
    OPCODE_TEXT = 0x01
    OPCODE_BINARY = 0x02
    OPCODE_CLOSE = 0x08
    OPCODE_PING = 0x09
    OPCODE_PONG = 0x0a

    HANDSHAKE_REQ = (
        'GET {} HTTP/1.1\r\n'
        'Upgrade: websocket\r\n'
        'Connection: Upgrade\r\n'
        'Sec-WebSocket-Key: {}\r\n'
        'Sec-WebSocket-Version: {}\r\n\r\n'
    )
    HANDSHAKE_RESP = (
        'HTTP/1.1 101 Switching Protocols\r\n'
        'Upgrade: websocket\r\n'
        'Connection: Upgrade\r\n'
        'Sec-WebSocket-Accept: {}\r\n\r\n'
    )

    def __init__(self, sock, client_side=False, resource='/'):
        super(WebSocket, self).__init__(sock, client_side)
        self.message = BytesIO()
        self.utf8validator = Utf8Validator()
        self.timeout = settings.PM_WEBSOCKET_TIMEOUT
        self.resource = resource
        if client_side:
            self.connecting_event = Event()
            self.is_connected = self._do_handshake()
            self.connecting_event.set()

    def _read_headers(self):
        headers = {}
        raw_readline = super(WebSocket, self).readline
        while 1:
            line = raw_readline(1024, self.timeout).strip()
            if not line:
                break
            key, value = line.split(':', 1)
            headers[key] = value.strip()
        return headers

    def _do_handshake(self):
        key = base64.b64encode(os.urandom(16)).decode('utf-8').strip()
        self._send_queue.append(
            self.HANDSHAKE_REQ.format(self.resource, key, self.VERSION)
        )
        self._send()
        line = super(WebSocket, self).readline(1024, self.timeout)
        if not line:
            self.close(reset=True)
            return False
        status = line.split(' ', 2)
        if len(status) != 3:
            self.close('invalid response line')
            return False
        status = int(status[1])
        if status != 101:
            self.close('handshake failed with status: %r' % status)
            return False

        headers = self._read_headers()

        if ('websocket' != headers.get('Upgrade') or
                'Upgrade' != headers.get('Connection')):
            self.close('invalid websocket handshake header')
            return False

        accept = headers.get("Sec-WebSocket-Accept", '').lower()
        if isinstance(accept, text_type):
            accept = accept.encode('utf-8')
        value = (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode('utf-8')
        hashed = base64.b64encode(sha1(value).digest()).strip().lower()
        if hashed != accept:
            self.close('invalid accept value')
            return False
        return True

    def _upgrade_connection(self):
        line = super(WebSocket, self).readline(1024, self.timeout)
        if not line:
            self.close(reset=True)
            return False

        datas = line.split()
        if len(datas) != 3:
            self.close('invalid request line: %r' % line)
            return False
        method, path, version = datas
        if method != 'GET' or version != 'HTTP/1.1':
            self.close('websocket requried GET HTTP/1.1, got `%s`' % line)
            return False

        headers = self._read_headers()

        sec_key = headers.get('Sec-WebSocket-Key', '')
        if not sec_key:
            self.close('no Sec-WebSocket-Key')
            return False

        version = headers.get('Sec-WebSocket-Version')
        if version not in self.SUPPORTED_VERSIONS:
            self.close('not supported version: %r' % version)
            return False

        resp_key = base64.b64encode(sha1(sec_key + self.GUID).digest())
        self._send_queue.append(self.HANDSHAKE_RESP.format(resp_key))
        self._send()
        return True

    def _write(self, packet_buffer, opcode):
        header = Header.encode_header(True, opcode, '', len(packet_buffer), 0)
        self._send_queue.append(header + packet_buffer)
        self._send()

    def oninit(self):
        """ Called by handler once handler start on a greenlet."""
        if self.client_side:
            self.connecting_event.wait()
            return self.is_connected
        else:
            return self._upgrade_connection()

    def handle_close(self, header, payload):
        """Called when a close frame has been decoded from the stream.

        :param header: The decoded `Header`.
        :param payload: The bytestring payload associated with the close frame.
        """
        if not payload:
            self.close(1000, None)
            return

        if len(payload) < 2:
            raise ProtocolError(
                'Invalid close frame: {0} {1}'.format(header, payload)
            )

        code = struct.unpack('!H', str(payload[:2]))[0]
        payload = payload[2:]

        if payload:
            val = self.utf8validator.validate(payload)
            if not val[0]:
                raise UnicodeError

        if (code < 1000 or 1004 <= code <= 1006 or 1012 <= code <= 1016 or
                code == 1100 or 2000 <= code <= 2999):
            raise ProtocolError('Invalid close code {0}'.format(code))
        self.close(code, payload)

    def handle_ping(self, header, payload):
        self.send_frame(payload, self.OPCODE_PONG)

    def handle_pong(self, header, payload):
        pass

    def read_frame(self):
        """Block until a full frame has been read from the socket.

        This is an internal method as calling this will not cleanup correctly
        if an exception is called. Use `receive` instead.

        :return: The header and payload as a tuple.
        """
        header = Header.decode_header(
            partial(super(WebSocket, self).read, timeout=self.timeout)
        )
        if not header:
            return header, ''

        if header.flags:
            raise ProtocolError

        if not header.length:
            return header, ''

        payload = super(WebSocket, self).read(header.length, self.timeout)
        if len(payload) != header.length:
            raise WebSocketError('Unexpected EOF reading frame payload')

        if header.mask:
            payload = header.unmask_payload(payload)
        return header, payload

    def read_message(self):
        """Return the next text or binary message from the socket.

        This is an internal method as calling this will not cleanup correctly
        if an exception is called. Use `receive` instead.
        """
        opcode = None
        message = ""

        while 1:
            header, payload = self.read_frame()
            if not header:
                break

            f_opcode = header.opcode
            if f_opcode in (self.OPCODE_TEXT, self.OPCODE_BINARY):
                # a new frame
                if opcode:
                    raise ProtocolError(
                        'The opcode in non-fin frame is expected to be zero,'
                        'got {0!r}'.format(f_opcode)
                    )

                # Start reading a new message, reset the validator
                self.utf8validator.reset()
                opcode = f_opcode
            elif f_opcode == self.OPCODE_CONTINUATION:
                if not opcode:
                    raise ProtocolError("Unexpected frame with opcode=0")
            elif f_opcode == self.OPCODE_PING:
                self.handle_ping(header, payload)
                continue
            elif f_opcode == self.OPCODE_PONG:
                self.handle_pong(header, payload)
                continue
            elif f_opcode == self.OPCODE_CLOSE:
                self.handle_close(header, payload)
                return
            else:
                raise ProtocolError("Unexpected opcode={0!r}".format(f_opcode))

            message += payload
            if header.fin:
                break

        if opcode == self.OPCODE_TEXT:
            stat = self.utf8validator.validate(message)
            if not stat[0]:
                raise UnicodeError(
                    "Encountered invalid UTF-8 while processing "
                    "text message at payload octet index {0:d}".format(stat[3])
                )
            return message
        else:
            return bytearray(message)

    def receive(self):
        """Read and return a message from the stream.

        If `None` is returned, then the socket is considered closed/errored.
        """

        try:
            return self.read_message()
        except UnicodeError:
            self.close(1007)
        except ProtocolError:
            self.close(1002)
        except socket_error:
            self.close()

    def read(self, size, timeout=None):
        buf = self.message
        buf.seek(0, 2)
        bufsize = buf.tell()
        self.message = BytesIO()
        if bufsize >= size:
            buf.seek(0)
            data = buf.read(size)
            self.message.write(buf.read())
            return data

        while 1:
            data = self.read_message()
            if not data:
                break
            n = len(data)
            if n == size and not bufsize:
                return data
            remain = size - bufsize
            if n >= remain:
                buf.write(data[:remain])
                self.message.write(data[remain:])
                break
            buf.write(data)
            bufsize += n
        return buf.getvalue()

    def readline(self, size, timeout=None):
        raise RuntimeError('websocket cannot readline')

    def send_frame(self, message, opcode):
        """Send a frame over the websocket with message as its payload."""
        if opcode == self.OPCODE_TEXT and isinstance(message, text_type):
            message = message.encode('utf-8')
        elif opcode == self.OPCODE_BINARY:
            message = str(message)
        self._write(message, opcode)

    def send(self, message, binary=True):
        """Send a frame over the websocket with message as its payload.

        pymaid need binary = True
        """
        if binary is None:
            binary = not isinstance(message, (str, unicode))  # noqa
        opcode = self.OPCODE_BINARY if binary else self.OPCODE_TEXT
        self.send_frame(message, opcode)

    @classmethod
    def connect(cls, address, client_side=True, timeout=None, _type=None):
        if not isinstance(address, string_types):
            raise ValueError('address should be string')
        sock = realsocket(AF_INET)
        # donot support wss yet
        hostname, port, resource, is_secure = parse_url(address)
        sock.connect((hostname, port))
        return cls(sock, client_side, resource)


class Header(object):

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
        self.mask = ''
        self.fin = fin
        self.opcode = opcode
        self.flags = flags
        self.length = length

    def mask_payload(self, payload):
        payload = bytearray(payload)
        mask = bytearray(self.mask)

        for i in xrange(self.length):  # noqa
            payload[i] ^= mask[i % 4]

        return str(payload)

    # it's the same operation
    unmask_payload = mask_payload

    def __repr__(self):
        return "<Header fin={} opcode={} length={} flags={} at 0x{:x}>".format(
            self.fin, self.opcode, self.length, self.flags, id(self)
        )

    @classmethod
    def decode_header(cls, raw_read):
        """Decode a WebSocket header.

        :param stream: A file like object that can be 'read' from.
        :returns: A `Header` instance.
        """
        data = raw_read(2)
        if not data:
            return

        if len(data) != 2:
            raise WebSocketError("Unexpected EOF while decoding header")

        first_byte, second_byte = struct.unpack('!BB', data)
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
                    "Received fragmented control frame: {0!r}".format(data)
                )
            # Control frames MUST have a payload length of 125 bytes or less
            if header.length > 125:
                raise FrameTooLargeException(
                    "Control frame cannot be larger than 125 bytes: "
                    "{0!r}".format(data)
                )

        if header.length == 126:
            # 16 bit length
            data = raw_read(2)
            if len(data) != 2:
                raise WebSocketError('Unexpected EOF while decoding header')
            header.length = struct.unpack('!H', data)[0]
        elif header.length == 127:
            # 64 bit length
            data = raw_read(8)
            if len(data) != 8:
                raise WebSocketError('Unexpected EOF while decoding header')
            header.length = struct.unpack('!Q', data)[0]

        if has_mask:
            mask = raw_read(4)
            if len(mask) != 4:
                raise WebSocketError('Unexpected EOF while decoding header')
            header.mask = mask
        return header

    @classmethod
    def encode_header(cls, fin, opcode, mask, length, flags):
        """Encodes a WebSocket header.

        :param fin: Whether this is the final frame for this opcode.
        :param opcode: The opcode of the payload, see `OPCODE_*`
        :param mask: Whether the payload is masked.
        :param length: The length of the frame.
        :param flags: The RSV* flags.
        :return: A bytestring encoded header.
        """
        first_byte = opcode
        second_byte = 0
        extra = ''

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
            extra = struct.pack('!H', length)
        elif length <= 0xffffffffffffffff:
            second_byte += 127
            extra = struct.pack('!Q', length)
        else:
            raise FrameTooLargeException

        if mask:
            second_byte |= cls.MASK_MASK
            extra += mask
        return chr(first_byte) + chr(second_byte) + extra
