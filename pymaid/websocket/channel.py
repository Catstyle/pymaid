from __future__ import absolute_import
__all__ = ['WSChannel']

from _socket import error as socket_error

from gevent import getcurrent, get_hub
from gevent.queue import Queue
from geventwebsocket.server import WebSocketServer

from pymaid.pb.channel import PBChannel
from pymaid.pb.controller import Controller
from pymaid.parser import unpack_packet, unpack_header, HEADER_LENGTH
from pymaid.error import RpcError
from pymaid.utils import greenlet_pool, pymaid_logger_wrapper
from pymaid.pb.pymaid_pb2 import Controller as PBC

from .proxy import WebSocketProxy

hub = get_hub()
REQUEST, RESPONSE, NOTIFICATION = PBC.REQUEST, PBC.RESPONSE, PBC.NOTIFICATION
RPCNotExist, PacketTooLarge = RpcError.RPCNotExist, RpcError.PacketTooLarge


@pymaid_logger_wrapper
class WSChannel(WebSocketServer, PBChannel):

    MAX_PACKET_LENGTH = 8 * 1024

    def __init__(self, listener, *args, **kwargs):
        if args:
            args = list(args)
            args[0] = self.connection_handler
        else:
            kwargs['application'] = self.connection_handler
        WebSocketServer.__init__(self, listener, *args, **kwargs)
        PBChannel.__init__(self)

    def _bind_connection_handler(self, conn):
        self.logger.info(
            '[conn|%d][host|%s][peer|%s] made',
            conn.conn_id, conn.sockname, conn.peername
        )

        current_gr = getcurrent()
        if current_gr != hub:
            conn.s_gr = current_gr
            conn.s_gr.link_exception(conn.close)

    def connect(self, address, timeout=None):
        # import here to avoid requirement when not using as client side
        import websocket
        ws = websocket.create_connection(address, timeout)
        conn = WebSocketProxy(self, ws)
        self._bind_connection_handler(conn)
        return conn

    def connection_handler(self, environ, start_response):
        ws = environ.get('wsgi.websocket')
        if not ws:
            start_response("400 Bad Request", [])
            return
        conn = WebSocketProxy(self, ws)
        self._bind_connection_handler(conn)
        self._connection_attached(conn)

        header_length, max_packet_length = HEADER_LENGTH, self.MAX_PACKET_LENGTH
        receive = conn.receive
        tasks_queue, handle_response = Queue(), self.handle_response
        gr = greenlet_pool.spawn(self.sequential_worker, tasks_queue)
        gr.link_exception(conn.close)

        callbacks = {
            REQUEST: self.handle_request,
            NOTIFICATION: self.handle_notification,
        }
        new_task = tasks_queue.put
        try:
            while 1:
                message = receive()
                if not message:
                    conn.close(reset=True)
                    break
                header = message[:header_length]
                parser_type, packet_length, content_length = unpack_header(header)
                if packet_length > max_packet_length:
                    conn.close(PacketTooLarge(packet_length=packet_length))
                    break

                controller_length = header_length + packet_length
                meta = unpack_packet(
                    message[header_length:controller_length], PBC, parser_type
                )
                controller = Controller(meta, parser_type)
                content = message[controller_length:controller_length+content_length]
                controller.conn = conn
                packet_type = controller.meta.packet_type
                if packet_type == RESPONSE:
                    handle_response(controller, content)
                else:
                    new_task((callbacks[packet_type], controller, content))
        except socket_error as ex:
            conn.close(ex, reset=True)
        except Exception as ex:
            conn.close(ex)
        finally:
            tasks_queue.queue.clear()
            new_task(None)
