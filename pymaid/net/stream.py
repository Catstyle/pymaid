import abc
import socket
import ssl as _ssl

from typing import Callable, List, Optional, TypeVar

from pymaid.types import DataType

from .transport import SocketTransport
from .utils.uri import URI


class Stream(SocketTransport):

    MAX_SIZE = 256 * 1024  # recv size passed to sock.recv
    KEEP_OPEN_ON_EOF = False

    WRAP_METHODS = {
        '_data_received': 'data_received',

        'write': '_write',
        'write_sync': '_write_sync',
    }

    def __init__(
        self,
        sock: socket.socket,
        *,
        on_open: Optional[List[Callable]] = None,
        on_close: Optional[List[Callable]] = None,
        initiative: bool = False,
        ssl_context: Optional[_ssl.SSLContext] = None,
        ssl_handshake_timeout: Optional[float] = None,
        uri: Optional[URI] = None,
    ):
        super().__init__(sock, on_open=on_open, on_close=on_close)
        self.initiative = initiative
        self.ssl_context = ssl_context
        self.ssl_handshake_timeout = ssl_handshake_timeout
        self.uri = uri

        self._write_empty_waiter = None

        self.wrap_methods()

    def wrap_methods(self):
        # for internal usage, can be overrided if needed
        for target, source in self.WRAP_METHODS.items():
            if not hasattr(self, target):
                setattr(self, target, getattr(self, source))

    async def wait_for_ready(self):
        '''Wait for connection made event if needed.'''
        if hasattr(self, 'conn_made_event'):
            await self.conn_made_event.wait()

    def _write_sync(self, data: DataType) -> bool:
        '''Write data to low level socket, in a synchronized way.

        Do some optimization by sending data directly if possible.
        Otherwise will add data to write_buffer, do it in write io Callable.

        There is another :meth:`write`, it will take care of write_buffer.

        :returns: bool, indicate whether sent out all data this time or not.
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
                    if self.state == self.STATE.CLOSING:
                        self._loop.call_soon(self._finnal_close, None)
                    return True
            # Not all was written; register write handler.
            self._loop.add_writer(self._sock_fd, self._writer)

        # Add it to the buffer.
        self.write_buffer.extend(data)
        return False

    async def _write(self, data: DataType):
        '''Write data to low level socket, in an asynchronized way.

        Do some optimization by sending data directly if possible.
        Otherwise will add data to write_buffer, do it in write io Callable.

        In order to deal with the issue of `handle backpressure correctly`_
        Will try to call await on the :meth:`wait_for_write_all` to wait for all
        buffered data to send.

        .. _handle backpressure correctly: https://vorpus.org/blog/some-thoughts-on-asynchronous-api-design-in-a-post-asyncawait-world/#bug-1-backpressure  # noqa
        '''
        if not self._write_sync(data):
            await self.wait_for_write_all()

    async def wait_for_write_all(self, timeout=None):
        '''Wait for all buffered data to send.

        Note: data added to the buffer during this period will be waited too.

        :params timeout: If passed an int or float, expressed in seconds, will
            cancel this method if sending not finished after that time. It is
            always relative to the current time.
        '''
        if not self.write_buffer:
            return
        if self._write_empty_waiter is not None:
            raise RuntimeError(
                'cannot call multiple wait_for_write_all at the same time'
            )
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

    # Public api for upper usage.
    @abc.abstractmethod
    def data_received(self, data: DataType):
        '''Callback when data received from low level transport.

        Upper level usage should always use this callback waiting for data.
        Should be overrided.
        '''
        self.logger.debug(
            f'{self!r} data_received, size={len(data)}, ignored!'
        )

    def eof_received(self) -> bool:
        '''Returned value indicate whether to keep the transport open or not.

        Default will close the transport.
        '''
        self.logger.debug(f'{self!r} eof_received')
        return self.KEEP_OPEN_ON_EOF

    # for internal
    def mark_ready(self):
        '''Hook to set conn_made_event.

        By default, this will directly set conn_made_event.
        Override it if needed.
        '''
        if hasattr(self, 'conn_made_event'):
            self.conn_made_event.set()
        self.logger.debug(f'{self!r} now ready to work')

        for cb in self.on_open:
            cb(self)

    def _reader(self):
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
                if self.eof_received() and not self.state < self.STATE.CLOSING:
                    # We're keeping the connection open so can write more,
                    # but we still can't receive more, so remove the reader.
                    self._loop.remove_reader(self._sock_fd)
                else:
                    self.close()
            except (SystemExit, KeyboardInterrupt):
                raise
            except BaseException as exc:
                self._fatal_error(exc, 'Fatal error: eof_received() failed.')
            return

        try:
            self._data_received(data)
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException as exc:
            self._fatal_error(exc, 'Fatal error: data_received() call failed.')

    def _writer(self):
        assert self.write_buffer, 'data should not be empty'

        try:
            n = self._sock.send(self.write_buffer)
        except (BlockingIOError, InterruptedError):
            pass
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException as exc:
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
