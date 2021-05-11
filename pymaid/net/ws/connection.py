from base64 import b64encode
from io import BytesIO
from os import urandom
from socket import error as socket_error

from pymaid.core import Event
from pymaid.net.stream import Stream
from pymaid.types import DataType
from pymaid.utils.logger import logger_wrapper

from .exceptions import ProtocolError
from .protocol import WSProtocol, Frame, unpack_H
from .utf8validator import Utf8Validator


@logger_wrapper
class WebSocket(Stream):
    '''A naive implementation of `websocket`_.

    .. _websocket: https://tools.ietf.org/html/rfc6455
    '''

    PROTOCOL = WSProtocol
    KEEP_OPEN_ON_EOF = True
    REQUIRE_MASK_CLIENT_FRAMES = True

    def __init__(
        self,
        sock,
        resource='/',
        *,
        on_open=None,
        on_close=None,
        initiative=False,
        ssl_context=None,
        ssl_handshake_timeout=None,
        **kwargs,
    ):
        super().__init__(
            sock,
            on_open=on_open,
            on_close=on_close,
            initiative=initiative,
            ssl_context=ssl_context,
            ssl_handshake_timeout=ssl_handshake_timeout,
        )
        self.conn_made_event = Event()
        self.resource = resource.encode('utf-8')
        self.ws_kwargs = kwargs
        self.utf8validator = Utf8Validator()
        self.__read_buffer = BytesIO()
        if self.initiative:
            self._start_handshake()
            self._parse = self._parse_upgrade_response
        else:
            self._parse = self._parse_upgrade_request
        self.on_close.append(self.cleanup)

    async def write(self, message: DataType):
        '''Send a frame over the websocket with message as its payload.'''
        await self._write(
            self.PROTOCOL.encode(
                message, self.get_mask_key() if self.need_mask else b''
            )
        )

    def write_sync(self, message: DataType):
        self._write_sync(self.PROTOCOL.encode(message))

    async def recv(self):
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

    def mark_ready(self):
        # we are finished upgrade handshake
        self.state = self.STATE.CONNECTED
        self.conn_made_event.set()
        self._parse = self._parse_frames

    def handle_close(self, frame):
        '''Called when a close frame has been decoded from the stream.

        :param frame: The decoded `Frame`.
        :param payload: The bytestring payload associated with the close frame.
        '''
        payload = frame.payload
        if not payload:
            self._write_sync(
                self.PROTOCOL.encode_frame(Frame.OPCODE_CLOSE, '')
            )
            self.close(1000)
            return

        if len(payload) < 2:
            raise ProtocolError(f'Invalid close frame: {frame} {payload}')

        status_code = payload[:2]
        payload = payload[2:]

        if payload:
            val = self.utf8validator.validate(payload)
            if not val[0]:
                raise UnicodeError

        code = unpack_H(status_code)[0]
        if (code < 1000 or 1004 <= code <= 1006 or 1012 <= code <= 1016
                or code == 1100 or 2000 <= code <= 2999):
            raise ProtocolError(f'Invalid close code {code}')
        self._write_sync(
            self.PROTOCOL.encode_frame(Frame.OPCODE_CLOSE, status_code),
        )
        self.close(code)

    def handle_ping(self, frame):
        self._write_sync(
            self.PROTOCOL.encode_frame(Frame.OPCODE_PONG, frame.payload)
        )

    def handle_pong(self, frame):
        pass

    def handle_frames(self, frames) -> bytes:
        '''Return the next text or binary message from the socket.

        This is an internal method as calling this will not cleanup correctly
        if an exception is called. Use :meth:`recv` instead.
        '''
        opcode = None
        message = []

        for frame in frames:

            if self.initiative and frame.mask:
                raise ProtocolError('masked server-to-client frame')
            elif not self.initiative and not frame.mask:
                raise ProtocolError('unmasked client-to-server frame')

            f_opcode = frame.opcode
            if f_opcode in (Frame.OPCODE_TEXT, Frame.OPCODE_BINARY):
                # a new frame
                if opcode:
                    raise ProtocolError(
                        f'The opcode in non-fin frame is expected to be zero, '
                        f'got {f_opcode}'
                    )

                # Start reading a new message, reset the validator
                self.utf8validator.reset()
                opcode = f_opcode
            elif f_opcode == Frame.OPCODE_CONTINUATION:
                if not opcode:
                    raise ProtocolError('Unexpected frame with opcode=0')
            elif f_opcode == Frame.OPCODE_PING:
                self.handle_ping(frame)
                continue
            elif f_opcode == Frame.OPCODE_PONG:
                self.handle_pong(frame)
                continue
            elif f_opcode == Frame.OPCODE_CLOSE:
                self.handle_close(frame)
                return
            else:
                raise ProtocolError(f'Unexpected opcode={f_opcode}')

            if frame.fin:
                opcode = None

            message.append(frame.payload)
        message = b''.join(message)

        if opcode == Frame.OPCODE_TEXT:
            stat = self.utf8validator.validate(message)
            if not stat[0]:
                raise UnicodeError(
                    f'Encountered invalid UTF-8 while processing '
                    f'text message at payload octet index {stat[3]}'
                )
            return message
        else:
            return message

    def get_mask_key(self):
        return urandom(4)

    @staticmethod
    def cleanup(self, exc=None):
        del self.__read_buffer

    @property
    def need_mask(self):
        '''All frames sent from the client to the server are masked by a 32-bit
        value that is contained within the frame.

        https://tools.ietf.org/html/rfc6455#section-5.3

        :NOTE: These rules might be relaxed in a future specification.
        '''
        return self.initiative and self.REQUIRE_MASK_CLIENT_FRAMES

    def _data_received(self, data: DataType):
        self.__read_buffer.seek(0, 2)
        self.__read_buffer.write(data)
        self._parse()

    def _parse_frames(self):
        '''Parse frames from incoming buffer.

        NOTE: correct frames will be lost if some frames are incorrect.
        '''
        buf = self.__read_buffer
        buf.seek(0, 0)

        used_size, frames = self.PROTOCOL.feed_data(buf)
        if frames:
            buf.seek(used_size, 0)
            self.__read_buffer = BytesIO()
            self.__read_buffer.write(buf.read())
            data = self.handle_frames(frames)
            if data:
                self.data_received(data)

    def _parse_upgrade_request(self) -> bool:
        buf = self.__read_buffer
        buf.seek(0, 0)

        resp = self.PROTOCOL.parse_request(buf)
        self._write_sync(resp)

        self.mark_ready()
        self.__read_buffer = BytesIO()
        self.__read_buffer.write(buf.read())
        return True

    def _parse_upgrade_response(self) -> bool:
        buf = self.__read_buffer
        buf.seek(0, 0)

        if not self.PROTOCOL.parse_response(buf, self.secret_key):
            return False

        self.mark_ready()
        self.__read_buffer = BytesIO()
        self.__read_buffer.write(buf.read())
        return True

    def _start_handshake(self):
        self.logger.debug(f'{self.id} start handshake')
        key = self.secret_key = b64encode(urandom(16)).strip()
        if isinstance(self.peername, str):
            host = self.peername.encode('utf-8')
        else:
            host = ('%s:%d' % self.peername).encode('utf-8')
        self._write_sync(
            self.PROTOCOL.build_request(
                host, self.resource, key, **self.ws_kwargs
            )
        )
