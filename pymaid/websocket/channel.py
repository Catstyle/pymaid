from __future__ import absolute_import
__all__ = ['WSChannel']

import six
from _socket import error as socket_error

from gevent import getcurrent, get_hub
from gevent.queue import Queue
from gevent.event import AsyncResult

from geventwebsocket.server import WebSocketServer
from google.protobuf.message import DecodeError

from pymaid.pb.controller import Controller
from pymaid.parser import unpack_header, HEADER_LENGTH
from pymaid.error import BaseError, ErrorMeta, RPCNotExist, PacketTooLarge
from pymaid.utils import greenlet_pool, pymaid_logger_wrapper
from pymaid.pb.pymaid_pb2 import Void, ErrorMessage, Controller as PBC

from .proxy import WebSocketProxy

hub = get_hub()
REQUEST, RESPONSE, NOTIFICATION = PBC.REQUEST, PBC.RESPONSE, PBC.NOTIFICATION


@pymaid_logger_wrapper
class WSChannel(WebSocketServer):

    MAX_PACKET_LENGTH = 8 * 1024

    def __init__(self, listener, *args, **kwargs):
        if args:
            args = list(args)
            args[0] = self.connection_handler
        else:
            kwargs['application'] = self.connection_handler
        super(WSChannel, self).__init__(listener, *args, **kwargs)

        self.services, self.service_methods, self.stub_response = {}, {}, {}
        self._get_rpc = self.service_methods.get
        self.connections = {}

    def _bind_connection_handler(self, conn):
        self.logger.info(
            '[conn|%d][host|%s][peer|%s] made',
            conn.conn_id, conn.sockname, conn.peername
        )

        current_gr = getcurrent()
        if current_gr != hub:
            conn.s_gr = current_gr
            conn.s_gr.link_exception(conn.close)

    def _connection_attached(self, conn):
        conn.set_close_cb(self._connection_detached)
        assert conn.conn_id not in self.connections
        self.connections[conn.conn_id] = conn
        self.connection_attached(conn)

    def _connection_detached(self, conn, reason=None):
        if not conn.server_side:
            for async_result in conn.transmissions.values():
                # we should not reach here with async_result left
                # that should be an exception
                async_result.set_exception(reason)
            conn.transmissions.clear()
        conn.s_gr.kill(block=False)
        assert conn.conn_id in self.connections
        del self.connections[conn.conn_id]
        self.connection_detached(conn, reason)

    def CallMethod(self, method, controller, request, response_class, callback):
        meta = controller.meta
        meta.service_method = method.full_name
        if not isinstance(request, Void):
            controller.pack_content(request)

        require_response = not issubclass(response_class, Void)
        if require_response:
            meta.packet_type = REQUEST
            transmission_id = controller.conn.transmission_id
            controller.conn.transmission_id += 1
            meta.transmission_id = transmission_id
        else:
            meta.packet_type = NOTIFICATION

        packet_buffer = controller.pack_packet()
        if controller.broadcast:
            # broadcast
            assert not require_response
            for conn in six.itervalues(self.connections):
                conn.send(packet_buffer, binary=1)
        elif controller.group is not None:
            # small broadcast
            assert not require_response
            get_conn = self.connections.get
            for conn_id in controller.group:
                conn = get_conn(conn_id)
                if conn:
                    conn.send(packet_buffer, binary=1)
        else:
            controller.conn.send(packet_buffer, binary=1)

        if not require_response:
            return

        self.stub_response[meta.service_method] = response_class
        async_result = AsyncResult()
        controller.conn.transmissions[transmission_id] = async_result
        return async_result.get()

    def connect(self, address, timeout=None):
        # import here to avoid requirement even not using as client side
        import websocket
        ws = websocket.create_connection(address, timeout)
        conn = WebSocketProxy(ws)
        self._bind_connection_handler(conn)
        return conn

    def append_service(self, service):
        assert service.DESCRIPTOR.full_name not in self.services
        self.services[service.DESCRIPTOR.full_name] = service
        service_methods = self.service_methods
        for method in service.DESCRIPTOR.methods:
            full_name = method.full_name
            assert full_name not in service_methods
            request_class = service.GetRequestClass(method)
            response_class = service.GetResponseClass(method)
            method = getattr(service, method.name)
            service_methods[full_name] = method, request_class, response_class
            # js/lua pb lib will format as '.service.method'
            service_methods['.'+full_name] = method, request_class, response_class

    def connection_attached(self, conn):
        pass

    def connection_detached(self, conn, reason):
        pass

    def connection_handler(self, environ, start_response):
        ws = environ.get('wsgi.websocket')
        if not ws:
            start_response("400 Bad Request", [])
            return
        conn = WebSocketProxy(ws)
        self._bind_connection_handler(conn)
        self._connection_attached(conn)

        header_length, max_packet_length = HEADER_LENGTH, self.MAX_PACKET_LENGTH
        receive, unpack_packet = conn.receive, Controller.unpack_packet
        tasks_queue, handle_response = Queue(), self.handle_response
        greenlet_pool.spawn(self.sequential_worker, tasks_queue)
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

                buf = message[header_length:header_length+packet_length+content_length]
                assert len(buf) == packet_length+content_length
                controller = unpack_packet(buf[:packet_length], parser_type)
                controller.content = buf[packet_length:]
                controller.conn = conn
                packet_type = controller.meta.packet_type
                if packet_type == RESPONSE:
                    handle_response(conn, controller)
                else:
                    new_task((callbacks[packet_type], conn, controller))
        except socket_error as ex:
            conn.close(ex, reset=True)
        except Exception as ex:
            conn.close(ex)
        finally:
            tasks_queue.queue.clear()
            new_task(None)

    def sequential_worker(self, tasks_queue):
        get_task = tasks_queue.get
        try:
            while 1:
                task = get_task()
                if not task:
                    break
                callback, conn, controller = task
                callback(conn, controller)
        except Exception as ex:
            conn.close(ex)

    def handle_request(self, conn, controller):
        controller.meta.packet_type = RESPONSE
        service_method = controller.meta.service_method

        rpc = self._get_rpc(service_method)
        if not rpc:
            controller.SetFailed(RPCNotExist(service_method=service_method))
            conn.send(controller.pack_packet(), binary=1)
            return

        method, request_class, response_class = rpc
        def send_response(response):
            assert response, 'rpc does not require a response of None'
            assert isinstance(response, response_class)
            controller.pack_content(response)
            conn.send(controller.pack_packet(), binary=1)

        request = controller.unpack_content(request_class)
        try:
            method(controller, request, send_response)
        except BaseError as ex:
            controller.SetFailed(ex)
            conn.send(controller.pack_packet(), binary=1)

    def handle_notification(self, conn, controller):
        service_method = controller.meta.service_method
        rpc = self._get_rpc(service_method)
        if not rpc:
            # failed silently when handle_notification
            return

        method, request_class, response_class = rpc
        request = controller.unpack_content(request_class)
        try:
            method(controller, request, lambda *args, **kwargs: '')
        except BaseError:
            # failed silently when handle_notification
            pass

    def handle_response(self, conn, controller):
        transmission_id = controller.meta.transmission_id
        assert transmission_id in conn.transmissions
        async_result = conn.transmissions.pop(transmission_id)

        if controller.Failed():
            error_message = controller.unpack_content(ErrorMessage)
            ex = ErrorMeta.get_by_code(error_message.error_code)()
            ex.message = error_message.error_message
            async_result.set_exception(ex)
        else:
            response_cls = self.stub_response[controller.meta.service_method]
            try:
                async_result.set(controller.unpack_content(response_cls))
            except DecodeError as ex:
                async_result.set_exception(ex)
