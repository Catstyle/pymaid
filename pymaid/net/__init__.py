'''pymaid separate network into two layer

transport layer
    transport layer concern about how data transmit
    for example: stream for tcp; packet for udp
    and security of transmission: with or without ssl/tls

protocol layer
    protocol layer concern about how app data format
    it does not care where the data comes from
    stream, packet, file, or pipeline are not different

    you feed it data, and it gives you protocol messages, that's all

    for example: http, protocol buffer, websocket
    and also has the ability to wrap builtin Protocols
    like AppProtocol(PBProtocol) or even AppProtocol(PBProtocol(WSProtocol))
'''

__all__ = ['Protocol', 'Transport', 'Stream', 'Datagram']

import abc
import socket

from typing import Any, Optional, Tuple, TypeVar

from pymaid.core import BaseTransport, Event
from pymaid.conf import settings
from pymaid.error.base import BaseEx
from pymaid.utils.logger import logger_wrapper

DataType = TypeVar('Data', bytes, memoryview)


class Protocol(metaclass=abc.ABCMeta):
    '''pymaid use Protocol representation app protocol layer

    You can build your protocol upon Protocol
    and you can easily change the underlying Protocol
    e.g.:
        build your AppProtocol inherit from Http and change to Http2 if wanted,
        and in best case, do not need to do anything else

        class AppProtocol(Http):
            ...

        class AppProtocol(Http2):
            ...
    '''

    @abc.abstractmethod
    def feed_data(self, data: DataType):
        raise NotImplementedError

    @abc.abstractmethod
    def encode(self, obj: Any) -> DataType:
        raise NotImplementedError

    @abc.abstractmethod
    def decode(self, data: DataType) -> Any:
        raise NotImplementedError


ProtocolType = TypeVar('Protocol', bound=Protocol)


@logger_wrapper
class Transport:
    '''pymaid use Transport representation transport layer '''

    CONN_ID = 0

    def __init__(self, *, channel=None, initiative=False):
        '''pymaid use Transport representation for transport layer

        transport layer donot care app protocol

        :params app_protocol: used to encode/decode protocol used by upper app
        '''
        self.channel = channel
        self.transport = None
        self.conn = None

        self.initiative = initiative
        self.exc = None
        self.conn_lost_event = Event()

        self.init()

    def init(self):
        pass

    def connection_made(self, transport: BaseTransport):
        self.__class__.CONN_ID = self.__class__.CONN_ID + 1
        self.conn_id = f'{self.__class__.__name__}-{self.__class__.CONN_ID}'
        self.bind_transport(transport)
        if self.channel:
            self.conn = self.channel.connection_made(self)
        self.logger.info(f'[{self}] made')

    def connection_lost(self, exc: Optional[Exception]):
        exc = exc or self.exc
        log = self.logger.info
        if exc:
            if isinstance(exc, (BaseEx, str, int)):
                log = self.logger.error
            else:
                log = self.logger.exception
        log('[%s] closed with [%r]', self, exc, exc_info=exc)
        if self.channel and self.conn:
            self.channel.connection_lost(self.conn, exc)
        self.destory()

    def close(self, exc: Optional[Exception] = None):
        self.exc = exc
        self.transport.close()

    def destory(self):
        self.channel = None
        self.transport = None
        self.conn = None
        self.write = None
        self.exc = None
        # when the conn_lost_event is set, the conn is destoryed
        # donot use it after return of waiting conn_lost_event
        self.conn_lost_event.set()

    def pause_writing(self):
        pass

    def resume_writing(self):
        pass

    def bind_transport(self, transport: BaseTransport):
        raise NotImplementedError

    def __repr__(self):
        return f'<{self.conn_id} initiative={self.initiative}>'


@logger_wrapper
class Stream(Transport):
    ''' raw stream transport '''

    def init(self):
        self.sockname = None
        self.peername = None

    def set_socket_default_options(self, sock):
        if sock.family == socket.AF_INET:
            setsockopt = sock.setsockopt
            getsockopt = sock.getsockopt
            SOL_SOCKET, SOL_TCP = socket.SOL_SOCKET, socket.SOL_TCP

            setsockopt(SOL_TCP, socket.TCP_NODELAY, 1)
            setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            ns = settings.namespaces['pymaid']  # should always exists
            if getsockopt(SOL_SOCKET, socket.SO_SNDBUF) < ns['SO_SNDBUF']:
                setsockopt(SOL_SOCKET, socket.SO_SNDBUF, ns['SO_SNDBUF'])
            if getsockopt(SOL_SOCKET, socket.SO_RCVBUF) < ns['SO_RCVBUF']:
                setsockopt(SOL_SOCKET, socket.SO_RCVBUF, ns['SO_RCVBUF'])

            if ns['PM_KEEPALIVE']:
                setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                setsockopt(SOL_TCP, socket.TCP_KEEPIDLE, ns['PM_KEEPIDLE'])
                setsockopt(SOL_TCP, socket.TCP_KEEPINTVL, ns['PM_KEEPINTVL'])
                setsockopt(SOL_TCP, socket.TCP_KEEPCNT, ns['PM_KEEPCNT'])

    def bind_transport(self, transport: BaseTransport):
        self.transport = transport
        self.sockname = transport.get_extra_info('sockname')
        self.peername = transport.get_extra_info('peername')

        if sock := self.transport.get_extra_info('socket'):
            self.set_socket_default_options(sock)

        self.write = transport.write
        self.can_write_eof = transport.can_write_eof
        self.shutdown = self.write_eof = transport.write_eof

    def data_received(self, data: bytes):
        # if conn is None, then this method should be override
        assert self.conn, 'this method should be override'
        self.conn.feed_data(data)

    def eof_received(self) -> Optional[bool]:
        # if conn is None, then this method should be override
        assert self.conn, 'this method should be override'
        return self.conn.feed_data(b'')

    def destory(self):
        super().destory()
        self.can_write_eof = None
        self.write_eof = None
        self.shutdown = None
        self.sockname = None
        self.peername = None

    def __repr__(self):
        return (
            f'<'
            f'{self.conn_id} initiative={self.initiative} '
            f'sockname={self.sockname} peername={self.peername}'
            f'>'
        )


@logger_wrapper
class Datagram(Transport):
    ''' raw datagram transport '''

    def bind_transport(self, transport: BaseTransport):
        self.transport = transport
        self.write = transport.sendto

    def can_write_eof(self):
        return False

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        if self.handler:
            self.handler.process(data, addr=addr)

    def error_received(self, exc: OSError):
        if self.handler:
            self.handler.process(b'')


TransportType = TypeVar('Transport', bound=Transport)
