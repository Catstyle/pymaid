from base64 import b64encode
from io import BytesIO
from os import urandom

from pymaid.core import Event
from pymaid.net.stream import Stream
from pymaid.net.utils.uri import URI
from pymaid.types import DataType
from pymaid.utils.logger import logger_wrapper

from .exceptions import ProtocolError
from .protocol import WSProtocol, Frame, CloseReason
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
        *,
        on_open=None,
        on_close=None,
        initiative=False,
        ssl_context=None,
        ssl_handshake_timeout=None,
        uri: URI = None,
        **kwargs,
    ):
        super().__init__(
            sock,
            on_open=on_open,
            on_close=on_close,
            initiative=initiative,
            ssl_context=ssl_context,
            ssl_handshake_timeout=ssl_handshake_timeout,
            uri=uri,
        )
        self.conn_made_event = Event()
        self.resource = ''
        if initiative:
            assert uri is not None
            self.resource = uri.path.encode('utf-8')
            if uri.query:
                self.resource = f'{uri.path}?{uri.query}'.encode('utf-8')
        self.ws_kwargs = kwargs
        self.__read_buffer = BytesIO()
        if self.initiative:
            self._start_handshake()
            self._parse = self._parse_upgrade_response
        else:
            self._parse = self._parse_upgrade_request
        self.on_close.append(self.cleanup)

        self.current_opcode = None
        self.current_message = []
        self.utf8validator = Utf8Validator()

    async def write(self, message: DataType):
        '''Send a frame over the websocket with message as its payload.'''
        await self._write(
            self.PROTOCOL.encode(
                message, self.get_mask_key() if self.need_mask else b''
            )
        )

    def write_sync(self, message: DataType):
        self._write_sync(
            self.PROTOCOL.encode(
                message, self.get_mask_key() if self.need_mask else b''
            )
        )

    def mark_ready(self):
        # we are finished upgrade handshake
        self.state = self.STATE.CONNECTED
        self.conn_made_event.set()
        self._parse = self._parse_frames

    def handle_close(self, frame: Frame):
        '''Called when a close frame has been decoded from the stream.

        :param frame: The decoded `Frame`.
        '''
        self._write_sync(
            self.PROTOCOL.encode_frame(Frame.OPCODE_CLOSE, frame.payload),
        )
        self.close(frame.close_reason)

    def handle_ping(self, frame: Frame):
        self._write_sync(
            self.PROTOCOL.encode_frame(Frame.OPCODE_PONG, frame.payload)
        )

    def handle_pong(self, frame: Frame):
        pass

    def get_mask_key(self) -> bytes:
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

        mbuf = buf.getbuffer()
        try:
            used_size, frames = self.PROTOCOL.feed_data(mbuf)
        finally:
            mbuf.release()
        if frames:
            buf.seek(used_size, 0)
            self.__read_buffer = BytesIO()
            self.__read_buffer.write(buf.read())
            try:
                self._handle_frames(frames)
            except ProtocolError as ex:
                self._write_sync(
                    self.PROTOCOL.encode_frame(
                        Frame.OPCODE_CLOSE,
                        ex.payload,
                        self.get_mask_key() if self.need_mask else b''
                    )
                )
                self.close(ex.reason)

    def _handle_frames(self, frames) -> bytes:
        opcode = self.current_opcode
        message = self.current_message
        data_received = self.data_received

        for frame in frames:

            if isinstance(frame, ProtocolError):
                raise frame

            if self.initiative and frame.mask:
                raise ProtocolError('masked server-to-client frame')
            elif not self.initiative and not frame.mask:
                raise ProtocolError('unmasked client-to-server frame')

            f_opcode = frame.opcode
            if f_opcode == Frame.OPCODE_TEXT:
                # a new frame
                if opcode:
                    raise ProtocolError(
                        f'The opcode in non-fin frame is expected to be zero, '
                        f'got {f_opcode}'
                    )
                opcode = f_opcode
                # Start reading a new message, reset the validator
                self.utf8validator.reset()
            elif f_opcode == Frame.OPCODE_BINARY:
                # a new frame
                if opcode:
                    raise ProtocolError(
                        f'The opcode in non-fin frame is expected to be zero, '
                        f'got {f_opcode}'
                    )
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

            if opcode == Frame.OPCODE_TEXT:
                # payload may be empty or one byte
                # making pyaload not a valid code point
                # need to used utf8validator instead
                resp = self.utf8validator.validate(frame.payload)
                if not resp[0]:
                    raise ProtocolError(
                        'Invalid UTF-8 payload',
                        CloseReason.INVALID_FRAME_PAYLOAD_DATA,
                    )
            message.append(frame.payload)

            if frame.fin:
                if opcode == Frame.OPCODE_TEXT:
                    data_received(b''.join(message).decode('utf-8'))
                else:
                    data_received(b''.join(message))
                opcode = None
                del message[:]

        self.current_opcode = opcode

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
        self._write_sync(
            self.PROTOCOL.build_request(
                self.uri.host.encode('utf-8'),
                self.resource,
                key,
                **self.ws_kwargs
            )
        )
