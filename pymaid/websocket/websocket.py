import struct
import base64

from io import BytesIO
from hashlib import sha1
from socket import error as socket_error

from pymaid.connection import Connection
from pymaid.utils import logger_wrapper

from .exceptions import ProtocolError, WebSocketError, FrameTooLargeException
from .utf8validator import Utf8Validator

__all__ = ['WebSocket']


@logger_wrapper
class WebSocket(Connection):

    SUPPORTED_VERSIONS = ('13', '8', '7')
    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    OPCODE_CONTINUATION = 0x00
    OPCODE_TEXT = 0x01
    OPCODE_BINARY = 0x02
    OPCODE_CLOSE = 0x08
    OPCODE_PING = 0x09
    OPCODE_PONG = 0x0a

    HANDSHAKE_RESP = (
        'HTTP/1.1 101 Switching Protocols\r\n'
        'Upgrade: websocket\r\n'
        'Connection: Upgrade\r\n'
        'Sec-WebSocket-Accept: {}\r\n\r\n'
    )

    def __init__(self, sock):
        super(WebSocket, self).__init__(sock)
        self.message = BytesIO()
        self.utf8validator = Utf8Validator()

    def _decode_bytes(self, bytestring):
        if not bytestring:
            return u''

        try:
            return bytestring.decode('utf-8')
        except UnicodeDecodeError:
            self.close(1007)
            raise

    def _encode_bytes(self, text):
        if isinstance(text, str):
            return text

        if not isinstance(text, unicode):  # noqa
            text = unicode(text or '')  # noqa
        return text.encode('utf-8')

    def _is_valid_close_code(self, code):
        # code == 1000: not sure about this but the autobahn fuzzer requires it
        if (code < 1000 or 1004 <= code <= 1006 or 1012 <= code <= 1016 or
                code == 1100 or 2000 <= code <= 2999):
            return False
        return True

    def oninit(self):
        """ Called by handler once handler start on a greenlet."""
        raw_readline = super(WebSocket, self).readline
        line = raw_readline(1024)
        if not line:
            self.close()
            return False

        datas = line.split()
        if len(datas) != 3:
            self.close('invalid request line')
            return False
        method, path, version = datas
        if method != 'GET' or version != 'HTTP/1.1':
            self.close('websocket requried GET HTTP/1.1, got `%s`' % line)
            return False

        headers = {}
        while 1:
            line = raw_readline(1024).strip()
            if not line:
                break
            key, value = line.split(':', 1)
            headers[key] = value.strip()

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
            validator = Utf8Validator()
            val = validator.validate(payload)
            if not val[0]:
                raise UnicodeError

        if not self._is_valid_close_code(code):
            raise ProtocolError('Invalid close code {0}'.format(code))
        self.close(code, payload)

    def handle_ping(self, header, payload):
        self.send_frame(payload, self.OPCODE_PONG)

    def handle_pong(self, header, payload):
        pass

    def validate_utf8(self, payload):
        # Make sure the frames are decodable independently
        self.utf8validate_last = self.utf8validator.validate(payload)
        if not self.utf8validate_last[0]:
            raise UnicodeError(
                "Encountered invalid UTF-8 while processing "
                "text message at payload octet index {0:d}".format(
                    self.utf8validate_last[3]
                )
            )

    def read_frame(self):
        """Block until a full frame has been read from the socket.

        This is an internal method as calling this will not cleanup correctly
        if an exception is called. Use `receive` instead.

        :return: The header and payload as a tuple.
        """
        header = Header.decode_header(super(WebSocket, self).read)
        if not header:
            return header, ''

        if header.flags:
            raise ProtocolError

        if not header.length:
            return header, ''

        payload = super(WebSocket, self).read(header.length)
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
                self.utf8validate_last = (True, True, 0, 0)
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
            self.validate_utf8(message)
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
        if opcode == self.OPCODE_TEXT:
            message = self._encode_bytes(message)
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
