__all__ = ['Connection']

import struct
import six
from io import BytesIO

from errno import EWOULDBLOCK, ECONNRESET, ENOTCONN, ESHUTDOWN
from _socket import (
    SOL_TCP, SOL_SOCKET, SO_LINGER, TCP_NODELAY, IPPROTO_TCP,
)

from gevent import getcurrent, get_hub
from gevent.greenlet import Greenlet
from gevent.queue import Queue
from gevent.socket import error as socket_error
from gevent.core import READ, WRITE, EVENTS

from pymaid.utils import greenlet_pool, pymaid_logger_wrapper
from pymaid.error import BaseError, EOF

range = six.moves.range
hub = get_hub()
io, timer = hub.loop.io, hub.loop.timer
del hub
invalid_conn_error = (ECONNRESET, ENOTCONN, ESHUTDOWN)


@pymaid_logger_wrapper
class Connection(object):

    CONN_ID = 1
    MAX_SEND = 5
    LINGER_PACK = struct.pack('ii', 1, 0)

    def __init__(self, channel, sock, server_side):
        self.channel = channel
        self.server_side = server_side
        self.transmission_id = 1

        self._setsockopt(sock)
        self._socket = sock
        self.peername = sock.getpeername()
        self.sockname = sock.getsockname()

        self.is_closed = False
        self.close_cb = None

        self.conn_id = self.CONN_ID
        Connection.CONN_ID += 1

        self.buf = BytesIO()
        self.transmissions = {}
        self._send_queue = Queue()

        self.r_io, self.w_io = io(sock.fileno(), READ), io(sock.fileno(), WRITE)
        self.r_gr, self.r_timer, self.feed_write = None, timer(0), False
        self.s_gr = greenlet_pool.spawn(channel.connection_handler, self)
        self.s_gr.link(self.close)

    def _setsockopt(self, sock):
        sock.setblocking(0)
        self.setsockopt = setsockopt = sock.setsockopt
        setsockopt(SOL_TCP, TCP_NODELAY, 1)
        setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
        setsockopt(SOL_SOCKET, SO_LINGER, self.LINGER_PACK)

    def _io_read(self):
        assert self.r_gr, 'nowhere to go'
        try:
            self.r_gr.switch()
        except Exception as ex:
            self.close(ex)

    def _io_write(self):
        send_queue = self._send_queue
        qsize = send_queue.qsize()
        if not qsize: 
            return

        send, queue = self._socket.send, send_queue.queue
        try:
            for _ in range(min(qsize, self.MAX_SEND)):
                buf = queue[0]
                # see pydoc of socket.send
                sent, bufsize = 0, len(buf)
                membuf = memoryview(buf)
                sent += send(membuf)
                while sent < bufsize:
                    sent += send(membuf[sent:])
                queue.popleft()
        except socket_error as ex:
            if ex.errno == EWOULDBLOCK:
                queue[0] = membuf[sent:]
                self.w_io.feed(WRITE, self._io_loop, EVENTS)
                self.feed_write = True
                return
            self.close(ex, reset=True)
        else:
            if qsize > self.MAX_SEND:
                self.w_io.feed(WRITE, self._io_loop, EVENTS)
                self.feed_write = True
            else:
                self.feed_write = False

    def _r_wait(self):
        self.r_io.start(self._io_read)
        try:
            self.r_gr.parent.switch()
        finally:
            self.r_io.stop()

    def _recv(self, buffers, size):
        recv_into, length = self._socket.recv_into, 0
        try:
            while 1:
                t = recv_into(buffers[length:])
                if not t:
                    raise EOF
                length += t
                if length >= size:
                    break
        except socket_error as ex:
            if ex.errno == EWOULDBLOCK:
                ret = length
            else:
                raise
        else:
            ret = length
        return ret

    def _read(self, size):
        buf = self.buf
        buf.seek(0, 2)
        bufsize = buf.tell()
        self.buf = BytesIO()  # reset self.buf.  we consume it via buf.
        if bufsize >= size:
            buf.seek(0)
            data = buf.read(size)
            self.buf.write(buf.read())
            return data
        recv, r_wait, length, remain = self._recv, self._r_wait, 0, size-bufsize
        membuf = memoryview(bytearray(remain))
        while 1:
            try:
                received = recv(membuf, remain)
            except socket_error as ex:
                self.close(ex, reset=True)
                if ex.errno in invalid_conn_error:
                    return ''
                raise
            if received == size and not bufsize:
                return membuf.tobytes()
            if received == remain:
                break
            else:
                # EWOULDBLOCK
                r_wait()
            remain -= received
        buf.write(membuf.tobytes())
        del membuf
        return buf.getvalue()

    def _readline(self, size):
        buf = self.buf
        buf.seek(0, 2)
        bufsize = buf.tell()
        self.buf = BytesIO()
        if bufsize:
            buf.seek(0)
            bline = buf.readline(size)
            if bline.endswith(b'\n') or len(bline) == size:
                self.buf.write(buf.read())
                return bline
            del bline
            buf.seek(0, 2)
        recv, r_wait, remain = self._recv, self._r_wait, size - bufsize
        received, bytebuf = 0, bytearray(remain)
        membytebuf = memoryview(bytebuf)
        while 1:
            try:
                rsize = recv(membytebuf, remain)
            except socket_error as ex:
                self.close(ex, reset=True)
                if ex.errno in invalid_conn_error:
                    return ''
                raise
            nl = bytebuf.find('\n', received, received+rsize)
            received += rsize
            if nl >= 0:
                nl += 1
                self.buf.write(membytebuf[nl:received].tobytes())
                if bufsize:
                    buf.write(membytebuf[:nl].tobytes())
                    break
                else:
                    return membytebuf[:nl].tobytes()
            if rsize == size and not bufsize:
                return membytebuf.tobytes()
            if rsize == remain:
                buf.write(membytebuf.tobytes())
                break
            else:
                # EWOULDBLOCK
                r_wait()
            remain -= rsize
        del membytebuf, bytebuf
        return buf.getvalue()

    def read(self, size, timeout=None):
        assert not self.r_gr, 'read conflict'
        self.r_gr = getcurrent()
        if not timeout:
            try:
                return self._read(size)
            finally:
                self.r_gr = None
        else:
            assert not self.r_timer, 'duplicated r_timer'
            self.r_timer = timer(timeout)
            self.r_timer.again(self._r_timeout)
            try:
                return self._read(size)
            finally:
                self.r_timer.stop()
                self.r_gr = self.r_timer = None

    def readline(self, size, timeout=None):
        assert not self.r_gr, 'read conflict'
        self.r_gr = getcurrent()
        if not timeout:
            try:
                return self._readline(size)
            finally:
                self.r_gr = None
        else:
            assert not self.r_timer, 'duplicated r_timer'
            self.r_timer = timer(timeout)
            self.r_timer.again(self._r_timeout)
            try:
                return self._readline(size)
            finally:
                self.r_timer.stop()
                self.r_gr = self.r_timer = None

    def write(self, packet_buffer):
        assert packet_buffer
        self._send_queue.put(packet_buffer)
        if not self.feed_write:
            self._io_write()
    send = write

    def close(self, reason=None, reset=False):
        if self.is_closed:
            return
        self.is_closed = True

        if isinstance(reason, Greenlet):
            reason = reason.exception

        if reason:
            if reset or isinstance(reason, BaseError):
                self.logger.error(
                    '[conn|%d][host|%s][peer|%s] closed with reason: %s',
                    self.conn_id, self.sockname, self.peername, reason
                )
            else:
                self.logger.exception(
                    '[conn|%d][host|%s][peer|%s] closed with reason: %s',
                    self.conn_id, self.sockname, self.peername, reason
                )
        else:
            self.logger.info(
                '[conn|%d][host|%s][peer|%s] closed cleanly',
                self.conn_id, self.sockname, self.peername
            )

        self._send_queue.queue.clear()
        self.s_gr.kill(block=True)
        self.w_io.stop()
        self.r_io.stop()
        self.r_timer.stop()
        self._socket.close()
        self.setsockopt = None
        self.buf = None

        if self.close_cb:
            self.close_cb(self, reason)
        self.close_cb = None

    def set_close_cb(self, close_cb):
        assert not self.close_cb
        assert callable(close_cb)
        self.close_cb = close_cb
