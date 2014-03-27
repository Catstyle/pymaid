import struct
from gevent.greenlet import Greenlet
from gevent.queue import Queue
from gevent import socket
from google.protobuf.message import DecodeError

import pymaid.logging
from pymaid.controller import Controller
from pymaid.utils import greenlet_pool

__all__ = ['Connection']


@pymaid.logging.class_wrapper
class Connection(object):
    '''
        Wrapper of BSD socket, which is packet oriented.
        Each packet with a fixed length header
        which describes the length of the packet,
        and is network order.
    '''

    HEADER = '!II'
    HEADER_LENGTH = struct.calcsize(HEADER)
    MAX_PACKET_LENGTH = 10 * 1024

    LINGER_PACK = struct.pack('ii', 1, 0)

    def __init__(self, sock):
        self.setsockopt(sock)
        self._peer_name = sock.getpeername()
        self._sock_name = sock.getsockname()
        self._socket = sock

        self._is_closed = False
        self._close_cb = None

        self._send_queue = Queue()
        self._recv_queue = Queue()

        self._send_let = greenlet_pool.spawn(self._send_loop)
        self._send_let.link(self.close)

        self._recv_let = greenlet_pool.spawn(self._recv_loop)
        self._recv_let.link(self.close)

    def setsockopt(self, sock):
        sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, self.LINGER_PACK)

    def send(self, packet_buff):
        '''
            Send would not block current greentlet.
        '''
        assert packet_buff
        self._send_queue.put(packet_buff)

    def recv(self, timeout=None):
        return self._recv_queue.get(timeout=timeout)

    def unlink_close(self):
        self._recv_let.unlink(self.close)
        self._send_let.unlink(self.close)

    def close(self, t=None):
        #print 'connection close', t
        if self._is_closed:
            return
        self._is_closed = True

        self.unlink_close()
        if t is not None and isinstance(t, Greenlet):
            reason = t.exception
        else:
            reason = t

        if reason is not None:
            self.logger.error(
                '[host|%s][peer|%s] closed with reason: %s',
                self.sockname, self.peername, reason
            )

        self._socket.close()
        if not self._send_let.dead:
            self._send_queue.put(None)
            self._send_let.kill(block=False)

        if not self._recv_let.dead:
            self._recv_queue.queue.clear()
            self._recv_queue.put((None, None))
            self._recv_let.kill(block=False)

        if self._close_cb:
            self._close_cb(self, reason)

    def set_close_cb(self, close_cb):
        assert self._close_cb is None
        assert callable(close_cb)
        self._close_cb = close_cb

    @property
    def sockname(self):
        return self._sock_name

    @property
    def peername(self):
        return self._peer_name

    @property
    def is_closed(self):
        return self._is_closed

    def _send_loop(self):
        '''
            Send loop should be run in another greenlet.
        '''
        get_packet, sendall = self._send_queue.get, self._socket.sendall
        pack = struct.pack
        while 1:
            controller = get_packet()
            if controller is None:
                break

            controller_buffer = controller.meta_data.SerializeToString()
            message_buffer = ""
            if not controller.Failed():
                if controller.meta_data.stub:
                    message = getattr(controller, "request", None)
                else:
                    message = getattr(controller, "response", None)

                if message is not None:
                    message_buffer = message.SerializeToString()

            header_buffer = pack(
                self.HEADER, len(controller_buffer), len(message_buffer)
            )
            try:
                # see pydoc of socket.sendall
                result = sendall(header_buffer+controller_buffer+message_buffer)
            except socket.error as ex:
                self.logger.error(
                    '[host|%s][peer|%s] send with exception: %s',
                    self.sockname, self.peername, ex
                )
                #traceback.print_exc()
                break
            if result is not None:
                break

    def _recv_n(self, nbytes):
        '''
            Receive specified @nbytes from socket.
            If have not recv specified nbytes, just return the
                partial buffer.
        '''
        recv, buff = self._socket.recv, ''
        while len(buff) < nbytes:
            try:
                t = recv(nbytes - len(buff))
                if not t:
                    self.logger.debug(
                        '[host|%s][peer|%s] has received EOF',
                        self.sockname, self.peername
                    )
                    return
                buff += t
            except socket.error as ex:
                self.logger.error(
                    '[host|%s][peer|%s] recv with exception: %s',
                    self.sockname, self.peername, ex
                )
                #traceback.print_exc()
                break
        return buff

    def _recv_loop(self):
        '''
            Receive a total integrated packet.
            If only recv partial, just return None.
        '''
        recv_n, unpack = self._recv_n, struct.unpack
        recv_package = self._recv_queue.put
        HEADER, MAX_PACKET_LENGTH = self.HEADER, self.MAX_PACKET_LENGTH
        while 1:
            header = recv_n(self.HEADER_LENGTH)
            if not header:
                break

            controller_length, message_length = unpack(HEADER, header)
            if controller_length + message_length >= MAX_PACKET_LENGTH:
                self.logger.error(
                    '[host|%s][peer|%s] closed with invalid payload [length|%d]',
                    self.sockname, self.peername, controller_length+message_length
                )
                return

            controller_buffer = recv_n(controller_length)
            controller = Controller()
            controller.conn = self
            try:
                controller.meta_data.ParseFromString(controller_buffer)
            except DecodeError as ex:
                self.logger.exception('process packet with decode error', ex)
                break

            message_buffer = ""
            if message_length > 0:
                message_buffer = recv_n(message_length)

            recv_package((controller, message_buffer))
