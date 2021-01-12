import struct

from base64 import b64encode
from functools import partial
from hashlib import sha1
from os import urandom
from socket import error as socket_error

from pymaid.conf import settings
from pymaid.core import create_task, BaseTransport, Event
from pymaid.net.stream import Stream
from pymaid.types import DataType
from pymaid.utils.logger import logger_wrapper

from .exceptions import ProtocolError, WebSocketError
from .protocol import unmask_payload, WSProtocol, Header
from .utf8validator import Utf8Validator


@logger_wrapper
class WebSocket(Stream):

    def __init__(self, *, server=None, initiative=False, resource='/'):
        super().__init__(server=server, initiative=initiative)
        self.utf8validator = Utf8Validator()
        self.timeout = settings.namespaces['pymaid']['PM_WEBSOCKET_TIMEOUT']
        self.resource = resource.encode('utf-8')
        self.protocol = WSProtocol()

    def _done_handshake(self, task):
        self.conn_made_event.set()
        if self.initiative:
            self.conn = self.server.connection_made(self)

    def _read_headers(self):
        headers = {}
        raw_readline = super(WebSocket, self).readline
        while 1:
            line = raw_readline(1024, self.timeout).strip()
            if not line:
                break
            key, value = line.split(b':', 1)
            headers[key] = value.strip()
        return headers

    def _do_handshake(self):
        self.logger.debug(f'{self.conn_id} doing handshake')
        key = b64encode(urandom(16)).strip()
        self.transport.write(self.protocol.handshake_frame(self.resource, key))
        line = super(WebSocket, self).readline(1024, self.timeout)
        if not line:
            self.close(reset=True)
            return False
        status = line.split(b' ', 2)
        if len(status) != 3:
            self.close('invalid response line')
            return False
        status = int(status[1])
        if status != 101:
            self.close(f'handshake failed with status: {status}')
            return False

        headers = self._read_headers()

        if (b'websocket' != headers.get(b'Upgrade')
                or b'Upgrade' != headers.get(b'Connection')):
            self.close('invalid websocket handshake header')
            return False

        accept = headers.get(b'Sec-WebSocket-Accept', '').lower()
        if isinstance(accept, str):
            accept = accept.encode('utf-8')
        value = key + b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
        hashed = b64encode(sha1(value).digest()).strip().lower()
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
            self.close(f'invalid request line: {line}')
            return False
        method, path, version = datas
        if method != b'GET' or version != b'HTTP/1.1':
            self.close(f'websocket requried GET HTTP/1.1, got `{line}`')
            return False

        headers = self._read_headers()

        sec_key = headers.get(b'Sec-WebSocket-Key', '')
        if not sec_key:
            self.close('no Sec-WebSocket-Key')
            return False

        version = headers.get(b'Sec-WebSocket-Version')
        if version not in self.SUPPORTED_VERSIONS:
            self.close(f'not supported version: {version}')
            return False

        resp_key = b64encode(sha1(sec_key + self.GUID).digest())
        self._send_queue.append(self.HANDSHAKE_RESP % resp_key)
        self._send()
        return True

    def _write(self, opcode: int, payload: DataType):
        self._send()

    def connection_made(self, transport: BaseTransport):
        self.__class__.CONN_ID = self.__class__.CONN_ID + 1
        self.conn_id = f'{self.__class__.__name__}-{self.__class__.CONN_ID}'
        self.bind_transport(transport)
        if self.initiative:
            self.conn_made_event = Event()
            self.handshake_handler = create_task(self._do_handshake())
            self.handshake_handler.add_done_callback(self.done_handshake)
        elif self.server:
            self.conn = self.server.connection_made(self)
        self.logger.info(f'[{self}] made')

    def oninit(self):
        ''' Called by handler once handler start on a greenlet.'''
        if self.initiative:
            self.connecting_event.wait()
            return self.is_connected
        else:
            return self._upgrade_connection()

    def handle_close(self, header, payload):
        '''Called when a close frame has been decoded from the stream.

        :param header: The decoded `Header`.
        :param payload: The bytestring payload associated with the close frame.
        '''
        if not payload:
            self.close(1000, None)
            return

        if len(payload) < 2:
            raise ProtocolError(f'Invalid close frame: {header} {payload}')

        code = struct.unpack('!H', payload[:2])[0]
        payload = payload[2:]

        if payload:
            val = self.utf8validator.validate(payload)
            if not val[0]:
                raise UnicodeError

        if (code < 1000 or 1004 <= code <= 1006 or 1012 <= code <= 1016
                or code == 1100 or 2000 <= code <= 2999):
            raise ProtocolError(f'Invalid close code {code}')
        self.close(code, payload)

    def handle_ping(self, header, payload):
        self.send_frame(payload, self.OPCODE_PONG)

    def handle_pong(self, header, payload):
        pass

    def read_frame(self):
        '''Block until a full frame has been read from the socket.

        This is an internal method as calling this will not cleanup correctly
        if an exception is called. Use `receive` instead.

        :return: The header and payload as a tuple.
        '''
        header = Header.decode_header(
            partial(super(WebSocket, self).read, timeout=self.timeout)
        )
        if not header:
            return header, b''

        if header.flags:
            raise ProtocolError(f'invalid flags: {header.flags}')

        if not header.length:
            return header, b''

        payload = super(WebSocket, self).read(header.length, self.timeout)
        if len(payload) != header.length:
            raise WebSocketError('Unexpected EOF reading frame payload')

        if header.mask:
            payload = unmask_payload(payload, header.mask)
        return header, payload

    def read_message(self):
        '''Return the next text or binary message from the socket.

        This is an internal method as calling this will not cleanup correctly
        if an exception is called. Use `receive` instead.
        '''
        opcode = None
        message = b''

        while 1:
            header, payload = self.read_frame()
            if not header:
                break

            f_opcode = header.opcode
            if f_opcode in (self.OPCODE_TEXT, self.OPCODE_BINARY):
                # a new frame
                if opcode:
                    raise ProtocolError(
                        f'The opcode in non-fin frame is expected to be zero,'
                        f'got {f_opcode}'
                    )

                # Start reading a new message, reset the validator
                self.utf8validator.reset()
                opcode = f_opcode
            elif f_opcode == self.OPCODE_CONTINUATION:
                if not opcode:
                    raise ProtocolError('Unexpected frame with opcode=0')
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
                raise ProtocolError(f'Unexpected opcode={f_opcode}')

            message += payload
            if header.fin:
                break

        if opcode == self.OPCODE_TEXT:
            stat = self.utf8validator.validate(message)
            if not stat[0]:
                raise UnicodeError(
                    f'Encountered invalid UTF-8 while processing '
                    f'text message at payload octet index {stat[3]}'
                )
            return message
        else:
            return message

    def receive(self):
        '''Read and return a message from the stream.

        If `None` is returned, then the socket is considered closed/errored.
        '''

        try:
            return self.read_message()
        except UnicodeError:
            self.close(1007)
        except ProtocolError:
            self.close(1002)
        except socket_error:
            self.close()
