import abc
import os
import socket
import ssl as _ssl
import sys

from typing import Callable, List, Optional, Tuple, TypeVar, Union

from pymaid.conf import settings
from pymaid.core import get_running_loop, CancelledError

from .base import logger, ChannelState
from .raw import sock_connect, sock_listen
from .stream import Stream


class Channel(abc.ABC):

    STATE = ChannelState
    logger = logger

    def __init__(self, *, address: Union[Tuple[str, int], str] = ''):
        '''Channel manages the sockets.'''
        self.address = address
        self.listeners = []
        self.state = self.STATE.CREATED
        self._loop = get_running_loop()
        self._serving_forever_fut = None

    async def listen(
        self,
        address: Union[Tuple[str, int], str],
        *,
        family: socket.AddressFamily = socket.AF_UNSPEC,
        flags: socket.AddressInfo = socket.AI_PASSIVE,
        backlog: int = 128,
        reuse_address: bool = os.name == 'posix' and sys.platform != 'cygwin',
        reuse_port: bool = False,
    ):
        listeners = await sock_listen(
            address,
            family=family,
            flags=flags,
            backlog=backlog,
            reuse_address=reuse_address,
            reuse_port=reuse_port,
        )
        for sock in listeners:
            self.listeners.append(sock)

    def read_from_listener(self, sock: socket.socket, backlog: int = 128):
        raise NotImplementedError

    async def wait_closed(self):
        pass

    async def serve_forever(self):
        if self._serving_forever_fut is not None:
            raise RuntimeError(
                f'channel {self!r} is already being awaited on serve_forever()'
            )
        if not self.listeners:
            raise RuntimeError(f'channel {self!r} has no listeners')

        self._serving_forever_fut = self._loop.create_future()

        try:
            await self._serving_forever_fut
        except CancelledError:
            try:
                self.close()
                await self.wait_closed()
            finally:
                raise
        finally:
            self._serving_forever_fut = None

    def start(self):
        if self.state >= self.STATE.CLOSING:
            raise RuntimeError(f'{self!r} is closing, cannot start again')
        self.logger.info(f'{self!r} start')
        self.state = self.STATE.STARTED
        loop = self._loop
        for sock in self.listeners:
            loop.add_reader(sock.fileno(), self.read_from_listener, sock)

    def pause(self, reason: str = ''):
        self.logger.info(f'{self!r} pause with reason: {reason}')
        self.state = self.STATE.PAUSED
        loop = self._loop
        for sock in self.listeners:
            loop.remove_reader(sock.fileno())

    def shutdown(self, reason: str = 'shutdown'):
        if self.state == self.STATE.CLOSING:
            return
        if self.state < self.STATE.PAUSED:
            self.pause(reason)
        self.state = self.STATE.CLOSING
        self.logger.info(f'{self!r} shutdown with reason: {reason}')

    def close(
        self, reason: Union[None, str, Exception] = 'called close',
    ):
        if self.state == self.STATE.CLOSED:
            return
        self.logger.info(f'{self!r} shutdown with reason: {reason}')
        if self.state == self.STATE.STARTED:
            self.pause(reason)
        if self.state == self.STATE.PAUSED:
            self.shutdown(reason)
        for sock in self.listeners:
            sock.close()
        del self.listeners[:]
        self.state = self.STATE.CLOSED

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        self.close(exc_val)
        await self.wait_closed()
        if exc_val:
            raise exc_val

    def __repr__(self):
        return (
            f'<Channel state={self.state.name} '
            f'listeners={len(self.listeners)}>'
        )


class StreamChannel(Channel):

    def __init__(
        self,
        *,
        address: Union[Tuple[str, int], str] = '',
        stream_class: Stream = Stream,
        ssl_context: _ssl.SSLContext,
        ssl_handshake_timeout: Optional[float] = None,
    ):
        super().__init__(address=address)
        self.stream_class = stream_class
        self.ssl_context = ssl_context
        self.ssl_handshake_timeout = ssl_handshake_timeout
        self.streams = {}

    @property
    def is_full(self):
        return len(self.streams) >= settings.pymaid.MAX_CONNECTIONS

    def read_from_listener(self, sock: socket.socket, backlog: int = 128):
        connection_made = self.connection_made
        for _ in range(backlog):
            if self.is_full:
                self.pause('{self!r} stop accept since is full')
                break
            try:
                conn, addr = sock.accept()
            except (BlockingIOError, InterruptedError, ConnectionAbortedError):
                return
            conn.setblocking(False)
            connection_made(conn)

    async def acquire(
        self,
        *,
        on_open: Optional[List[Callable]] = None,
        on_close: Optional[List[Callable]] = None,
    ) -> Stream:
        sock = await sock_connect(self.address)
        self.logger.info(f'{self!r} acquire: {sock=}')
        return self.make_connection(sock, True, on_open, on_close)

    def make_connection(self, sock, initiative, on_open=None, on_close=None):
        return self.stream_class(
            sock,
            initiative=initiative,
            ssl_context=self.ssl_context,
            ssl_handshake_timeout=self.ssl_handshake_timeout,
            on_open=on_open,
            on_close=on_close,
        )

    def connection_made(self, sock: socket.socket) -> Stream:
        self.logger.info(f'{self!r} connection_made: {sock=}')
        stream = self.make_connection(
            sock, False, on_close=[self.connection_lost],
        )
        self.streams[stream.id] = stream
        return stream

    def connection_lost(self, stream: Stream, exc=None):
        self.logger.info(f'{self!r} connection_lost: {stream=} {exc=}')
        assert stream.id in self.streams, (stream.id, self.streams.keys())
        del self.streams[stream.id]

    def shutdown(self, reason: str = 'shutdown'):
        super().shutdown(reason)
        for stream in self.streams.values():
            # stream.shutdown is not coroutine
            stream.shutdown(reason)


ChannelType = TypeVar('ChannelType', bound=Channel)
