import abc
import enum
import socket
import warnings

from typing import Callable, List, Optional, TypeVar

from pymaid.core import get_running_loop, Event
from pymaid.utils.logger import get_logger

logger = get_logger('pymaid.net.stream')


class TransportState(enum.IntEnum):

    UNKNOWN = 0
    OPENED = 10
    CLOSING = 20
    CLOSED = 30


class ChannelState(enum.IntEnum):

    CREATED = 0
    STARTED = 10
    PAUSED = 20
    CLOSING = 30
    CLOSED = 40


class Transport(abc.ABC):

    logger = logger
    ID = 1

    def _fatal_error(self, exc, message='Fatal error on transport'):
        # Should be called from exception handler only.
        if isinstance(exc, OSError):
            self.logger.debug("%r: %s", self, message, exc_info=True)
        else:
            self._loop.call_exception_handler({
                'message': message,
                'exception': exc,
                'socket': self._sock,
            })
        self._force_close(exc)


class SocketTransport(Transport):
    '''Base class for net transport.

    Wraps low level socket.
    Wrapped some attrs and methods, added some apis like `asyncio` `protocols`.
    '''

    WRAPPED_ATTRS = ('family', 'proto', 'timeout', 'type')
    WRAPPED_METHODS = ('getsockopt', 'setsockopt')
    STATE = TransportState

    BUFFER_FACTORY = bytearray

    def __init__(
        self,
        sock: socket.socket,
        *,
        on_open: Optional[List[Callable]] = None,
        on_close: Optional[List[Callable]] = None,
    ):
        self._loop = get_running_loop()
        self.wrap_sock(sock)
        self.id = self.__class__.ID
        self.__class__.ID += 1

        self.on_open = on_open or []
        self.on_close = on_close or []
        self.closed_event = Event()
        self.state = self.STATE.OPENED
        self.write_buffer = self.BUFFER_FACTORY()

    def wrap_sock(self, sock: socket.socket):
        self._sock = sock
        self._sock_fd = sock.fileno()
        self._wrap_sock(self.WRAPPED_ATTRS)
        self._wrap_sock(self.WRAPPED_METHODS)
        self.set_socket_default_options()

        self.peername = sock.getpeername()
        self.sockname = sock.getsockname()
        self._loop.add_reader(self._sock_fd, self._read_ready)

    def set_socket_default_options(self):
        pass

    def shutdown(self, reason=None):
        self._loop.remove_writer(self._sock_fd)
        self._sock.shutdown(socket.SHUT_WR)

    def close(self, exc=None):
        if self.state == self.STATE.CLOSING:
            return
        self.state = self.STATE.CLOSING
        loop = self._loop
        loop.remove_reader(self._sock_fd)

        if not self.write_buffer:
            loop.remove_writer(self._sock_fd)
            # loop.call_soon(self._finnal_close, None)
            self._finnal_close(exc)

    async def wait_closed(self):
        await self.closed_event.wait()

    def _wrap_sock(self, keys: List[str]):
        for key in keys:
            setattr(self, key, getattr(self._sock, key))

    def _force_close(self, exc):
        if self.state == self.STATE.CLOSED:
            return
        if self.write_buffer:
            self.write_buffer.clear()
            self._loop.remove_writer(self._sock_fd)
        self._loop.remove_reader(self._sock_fd)
        # self._loop.call_soon(self._finnal_close, exc)
        self._finnal_close(exc)

    def _finnal_close(self, exc=None):
        self.logger.info(f'{self!r} final close {exc=}')
        self.state = self.STATE.CLOSED
        for cb in self.on_close:
            cb(self, exc)
        self._sock.close()
        self._sock = None
        self._loop = None
        del self.on_open
        del self.on_close
        self.closed_event.set()

    def __del__(self, _warn=warnings.warn):
        if getattr(self, '_sock', None):
            _warn(f'unclosed transport {self!r}', ResourceWarning, source=self)
            self._sock.close()
            self._sock = None

    def __repr__(self):
        return (
            f'<{self.__class__.__name__} id={self.id} sock_fd={self._sock_fd} '
            f'state={self.state.name} initiative={self.initiative} '
            f'sockname={self.sockname} peername={self.peername}'
            f'>'
        )


TransportType = TypeVar('TransportType', bound=Transport)
