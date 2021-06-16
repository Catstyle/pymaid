import abc
import os
import socket
import ssl as _ssl
import sys

from typing import Optional, TypeVar, Union

from pymaid.conf import settings
from pymaid.core import get_running_loop, Event, CancelledError
from pymaid.ext.middleware import MiddlewareManager

from .base import logger, ChannelState
from .raw import sock_listen
from .stream import Stream, StreamType
from .transport import Transport, TransportType


class Channel(abc.ABC):

    STATE = ChannelState
    logger = logger

    def __init__(
        self,
        *,
        name: str = 'Channel',
        transport_class: TransportType = Transport,
        ssl_context: _ssl.SSLContext,
        ssl_handshake_timeout: Optional[float] = None,
        middleware_manager: Optional[MiddlewareManager] = None,
        **kwargs,
    ):
        '''Channel manages the sockets.'''
        self.name = name
        self.transport_class = transport_class
        self.ssl_context = ssl_context
        self.ssl_handshake_timeout = ssl_handshake_timeout

        self.transports = {}
        self.listeners = []
        self.middleware_manager = middleware_manager or MiddlewareManager()
        self.extra_transport_kwargs = kwargs

        self.state = self.STATE.CREATED
        self.nursed = False
        self.closed_event = Event()
        self._loop = get_running_loop()
        self._serving_forever_fut = None

    @property
    def is_full(self):
        return len(self.transports) >= settings.pymaid.MAX_CONNECTIONS

    async def listen(
        self,
        net: str,
        address: str,
        *,
        family: socket.AddressFamily = socket.AF_UNSPEC,
        flags: socket.AddressInfo = socket.AI_PASSIVE,
        backlog: int = 128,
        reuse_address: bool = os.name == 'posix' and sys.platform != 'cygwin',
        reuse_port: bool = False,
    ):
        listeners = await sock_listen(
            net,
            address,
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
        await self.closed_event.wait()

    async def serve_forever(self):
        if self._serving_forever_fut is not None:
            raise RuntimeError(
                f'channel {self!r} is already being awaited on serve_forever()'
            )
        if not self.listeners:
            raise RuntimeError(f'channel {self!r} has no listeners')

        if not self.nursed:
            raise RuntimeError(
                'you should wrap this channel into async context manager, like'
                '''
    async with ch:
        await ch.serve_forever()'''
            )

        self._serving_forever_fut = self._loop.create_future()

        try:
            await self._serving_forever_fut
        except CancelledError:
            # received CancelledError when event loop exit
            pass
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
        self.logger.info(f'{self!r} pause with reason: {reason!r}')
        self.state = self.STATE.PAUSED
        loop = self._loop
        for sock in self.listeners:
            loop.remove_reader(sock.fileno())

    def shutdown(self, reason: str = 'shutdown'):
        if self.state >= self.STATE.SHUTTING_DOWN:
            return
        if self.state < self.STATE.PAUSED:
            self.pause(reason)
        self.logger.info(f'{self!r} shutdown with reason: {reason!r}')
        self.state = self.STATE.SHUTTING_DOWN

    def close(
        self, reason: Union[None, str, Exception] = 'called close',
    ):
        if self.state >= self.STATE.CLOSING:
            return
        if self.state == self.STATE.STARTED:
            self.pause(reason)
        if self.state == self.STATE.PAUSED:
            self.shutdown(reason)
        self.logger.info(f'{self!r} close with reason: {reason!r}')
        self.state = self.STATE.CLOSING
        for sock in self.listeners:
            sock.close()
        del self.listeners[:]
        if not self.transports:
            self._finnal_close(reason)

    def _finnal_close(self, reason=None):
        self.closed_event.set()
        self.logger.info(f'{self!r} finally closed with reason: {reason!r}')
        self.state = self.STATE.CLOSED

    async def __aenter__(self):
        self.nursed = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(exc_val)
        self.close(exc_val)
        await self.wait_closed()
        if exc_val:
            raise exc_val

    def __repr__(self):
        return (
            '<'
            f'{self.name} '
            f'state={self.state.name} '
            f'listeners={len(self.listeners)} '
            f'transports={len(self.transports)} '
            f'middlewares={len(self.middleware_manager.middlewares)}'
            '>'
        )


class StreamChannel(Channel):

    def __init__(
        self,
        *,
        name: str = 'StreamChannel',
        transport_class: StreamType = Stream,
        ssl_context: _ssl.SSLContext,
        ssl_handshake_timeout: Optional[float] = None,
        middleware_manager: Optional[MiddlewareManager] = None,
        **kwargs,
    ):
        super().__init__(
            name=name,
            transport_class=transport_class,
            ssl_context=ssl_context,
            ssl_handshake_timeout=ssl_handshake_timeout,
            middleware_manager=middleware_manager,
            **kwargs,
        )

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

    def connection_made(self, sock: socket.socket) -> Stream:
        conn = self._make_connection(
            sock, False, on_close=[self.connection_lost],
        )
        self.transports[conn.id] = conn
        self.logger.info(
            f'{self!r} connection_made: '
            f'<{self.transport_class.__name__} {conn.id}>'
        )
        return conn

    def connection_lost(self, conn: Stream, exc=None):
        assert conn.id in self.transports, conn.id
        del self.transports[conn.id]
        if self.state == self.STATE.PAUSED and not self.is_full:
            self.start()
        if not self.transports and self.state >= self.STATE.CLOSING:
            self._finnal_close(exc)
        self.logger.info(
            f'{self!r} connection_lost: '
            f'<{self.transport_class.__name__} {conn.id}> exc={exc}'
        )

    def shutdown(self, reason: str = 'shutdown'):
        super().shutdown(reason)
        for conn in self.transports.values():
            # conn.shutdown is not coroutine
            conn.shutdown(reason)

    def _make_connection(self, sock, initiative, on_open=None, on_close=None):
        return self.transport_class(
            sock,
            initiative=initiative,
            ssl_context=self.ssl_context,
            ssl_handshake_timeout=self.ssl_handshake_timeout,
            on_open=on_open,
            on_close=on_close,
            **self.extra_transport_kwargs,
        )


ChannelType = TypeVar('ChannelType', bound=Channel)
