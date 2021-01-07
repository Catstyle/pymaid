import socket
import ssl as _ssl

from typing import Callable, List, Optional, TypeVar

from pymaid.conf import settings
from pymaid.types import DataType

from .base import SocketTransport


class Stream(SocketTransport):

    MAX_SIZE = 256 * 1024  # recv size passed to sock.recv
    KEEP_OPEN_ON_EOF = False

    def __init__(
        self,
        sock: socket.socket,
        *,
        on_open: Optional[List[Callable]] = None,
        on_close: Optional[List[Callable]] = None,
        initiative: bool = False,
        ssl_context: Optional[_ssl.SSLContext] = None,
        ssl_handshake_timeout: Optional[float] = None,
    ):
        super().__init__(sock, on_open=on_open, on_close=on_close)
        self.initiative = initiative
        self.ssl_context = ssl_context
        self.ssl_handshake_timeout = ssl_handshake_timeout
        self._write_empty_waiter = None

        for cb in self.on_open:
            cb(self)

    def set_socket_default_options(self):
        super().set_socket_default_options()
        sock = self._sock
        assert sock.type == socket.SOCK_STREAM

        setsockopt = sock.setsockopt
        getsockopt = sock.getsockopt
        SOL_SOCKET, SOL_TCP = socket.SOL_SOCKET, socket.SOL_TCP

        if sock.family != socket.AF_UNIX:
            setsockopt(SOL_TCP, socket.TCP_NODELAY, 1)
            setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        ns = settings.namespaces['pymaid']  # should always exists
        if getsockopt(SOL_SOCKET, socket.SO_SNDBUF) < ns['SO_SNDBUF']:
            setsockopt(SOL_SOCKET, socket.SO_SNDBUF, ns['SO_SNDBUF'])
        if getsockopt(SOL_SOCKET, socket.SO_RCVBUF) < ns['SO_RCVBUF']:
            setsockopt(SOL_SOCKET, socket.SO_RCVBUF, ns['SO_RCVBUF'])

        if sock.family != socket.AF_UNIX and ns['PM_KEEPALIVE']:
            setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            setsockopt(SOL_TCP, socket.TCP_KEEPIDLE, ns['PM_KEEPIDLE'])
            setsockopt(SOL_TCP, socket.TCP_KEEPINTVL, ns['PM_KEEPINTVL'])
            setsockopt(SOL_TCP, socket.TCP_KEEPCNT, ns['PM_KEEPCNT'])

    def write_sync(self, data: DataType) -> bool:
        '''Write data to low level socket, in a synchronized way.

        Do some optimization by sending data directly if possible.
        Otherwise will add data to write_buffer, do it in write io Callable.

        There is another :meth:`write`, it will take care of write_buffer.

        :rvalue: indicate whether sent out all data this time.
        '''
        if not self.write_buffer:
            # Optimization: try to send now.
            try:
                n = self._sock.send(data)
            except (BlockingIOError, InterruptedError):
                pass
            except (SystemExit, KeyboardInterrupt):
                raise
            except BaseException as exc:
                self._fatal_error(exc, 'Fatal write error on socket transport')
                return
            else:
                data = data[n:]
                if not data:
                    return True
            # Not all was written; register write handler.
            self._loop.add_writer(self._sock_fd, self._write_ready)

        # Add it to the buffer.
        self.write_buffer.extend(data)
        return False

    async def write(self, data: DataType):
        '''Write data to low level socket, in an asynchronized way.

        Do some optimization by sending data directly if possible.
        Otherwise will add data to write_buffer, do it in write io Callable.

        In order to deal with the issue of `handle backpressure correctly`_
        Will try to call await on the :meth:`wait_write_all` to wait for all
        buffered data to send.

        .. _handle backpressure correctly: https://vorpus.org/blog/some-thoughts-on-asynchronous-api-design-in-a-post-asyncawait-world/#bug-1-backpressure  # noqa
        '''
        if not self.write_sync(data):
            await self.wait_write_all()

    async def wait_write_all(self, timeout=None):
        '''Wait for all buffered data to send.

        Note: data added to the buffer during this period will be waited too.

        :params timeout: If passed an int or float, expressed in seconds, will
            cancel this method if sending not finished after that time. It is
            always relative to the current time.
        '''
        if not self.write_buffer:
            return
        if self._write_empty_waiter is not None:
            raise RuntimeError('wait_write_all has been called')
        self._write_empty_waiter = self._loop.create_future()
        if timeout is not None:
            timer = self._loop.call_later(
                timeout, self._write_empty_waiter.cancel
            )
        try:
            await self._write_empty_waiter
        finally:
            if timeout is not None:
                timer.cancel()
            self._write_empty_waiter = None

    def data_received(self, data: DataType):
        self.logger.debug(f'{self!r} data_received, {len(data)=}, ignored!')

    def eof_received(self) -> bool:
        '''Returned value indicate whether to keep the transport open or not.

        Default will close the transport.
        '''
        self.logger.debug(f'{self!r} eof_received')
        return self.KEEP_OPEN_ON_EOF

    def _read_ready(self):
        try:
            data = self._sock.recv(self.MAX_SIZE)
        except (BlockingIOError, InterruptedError):
            return
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException as exc:
            self._fatal_error(exc, 'Fatal read error on socket transport')
            return

        if not data:
            try:
                if self.eof_received():
                    # We're keeping the connection open so the
                    # protocol can write more, but we still can't
                    # receive more, so remove the reader Callable.
                    self._loop.remove_reader(self._sock_fd)
                else:
                    self.close()
            except (SystemExit, KeyboardInterrupt):
                raise
            except BaseException as exc:
                self._fatal_error(exc, 'Fatal error: eof_received() failed.')
            return

        try:
            self.data_received(data)
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException as exc:
            self._fatal_error(
                exc, 'Fatal error: stream.data_received() call failed.'
            )

    def _write_ready(self):
        assert self.write_buffer, 'data should not be empty'

        try:
            n = self._sock.send(self.write_buffer)
        except (BlockingIOError, InterruptedError):
            pass
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException as exc:
            self._loop.remove_writer(self._sock_fd)
            self.write_buffer.clear()
            self._fatal_error(exc, 'Fatal write error on socket transport')
        else:
            if n:
                del self.write_buffer[:n]
            if not self.write_buffer:
                self._loop.remove_writer(self._sock_fd)
                if self._write_empty_waiter:
                    self._write_empty_waiter.set_result(None)
                    self._write_empty_waiter = None
                if self.state == self.STATE.CLOSING:
                    self._finnal_close(None)


StreamType = TypeVar('StreamType', bound=Stream)
