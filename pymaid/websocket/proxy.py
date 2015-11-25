__all__ = ['WebSocketProxy']

import struct

from errno import EINVAL, ENOTCONN
from _socket import error as socket_error

from gevent.greenlet import Greenlet

from pymaid.utils import pymaid_logger_wrapper
from pymaid.error.base import BaseEx


@pymaid_logger_wrapper
class WebSocketProxy(object):

    CONN_ID = 1
    LINGER_PACK = struct.pack('ii', 1, 0)

    def __init__(self, channel, ws):
        self.channel = channel
        self.ws = ws
        self._socket = ws.handler.socket
        self.transmission_id, self.transmissions = 1, {}
        self.is_closed, self.close_cb = False, None
        self.server_side = False

        self.conn_id = self.CONN_ID
        WebSocketProxy.CONN_ID += 1

    @property
    def peername(self):
        try:
            return self._socket.getpeername()
        except socket_error as err:
            if err.errno == EINVAL:
                return 'invalid in shutdown socket on osx'
            elif err.errno == ENOTCONN:
                return 'ENOTCONN'
            raise

    @property
    def sockname(self):
        return self._socket.getsockname()

    @property
    def fd(self):
        return self._socket.fileno()

    def send(self, data, binary=1):
        return self.ws.send(data, binary)

    def set_close_cb(self, close_cb):
        assert not self.close_cb
        assert callable(close_cb)
        self.close_cb = close_cb

    def close(self, reason=None, reset=False):
        if self.is_closed:
            return
        self.is_closed = True

        if isinstance(reason, Greenlet):
            reason = reason.exception

        if reason:
            if reset or isinstance(reason, BaseEx):
                log = self.logger.error
            else:
                log = self.logger.exception
        else:
            log = self.logger.info
        log('[conn|%d][host|%s][peer|%s] closed with reason: %r',
            self.conn_id, self.sockname, self.peername, reason)

        self.ws.close()

        if self.close_cb:
            self.close_cb(self, reason)
        self.close_cb = None

    def __getattr__(self, name):
        return getattr(self.ws, name)
