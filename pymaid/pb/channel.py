__all__ = ['PBChannel']

import six
from _socket import error as socket_error

from gevent.queue import Queue
from gevent.event import AsyncResult

from google.protobuf.message import DecodeError

from pymaid.channel import Channel
from pymaid.pb.controller import Controller
from pymaid.parser import (
    unpack_header, HEADER_LENGTH, REQUEST, RESPONSE, NOTIFICATION
)
from pymaid.error import BaseError, ErrorMeta, RPCNotExist, PacketTooLarge
from pymaid.utils import greenlet_pool, pymaid_logger_wrapper
from pymaid.pb.pymaid_pb2 import Void, ErrorMessage

range = six.moves.range


@pymaid_logger_wrapper
class PBChannel(Channel):

    MAX_PACKET_LENGTH = 8 * 1024

    def __init__(self, loop=None):
        super(PBChannel, self).__init__(loop)
        self.services, self.service_methods, self.stub_response = {}, {}, {}

    def _connection_detached(self, conn, reason):
        conn.s_gr.kill(block=False)
        if not conn.server_side:
            for async_result in conn.transmissions.values():
                # we should not reach here with async_result left
                # that should be an exception
                async_result.set_exception(reason)
            conn.transmissions.clear()
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
            for conn in six.itervalues(self.incoming_connections):
                conn.send(packet_buffer)
        elif controller.group:
            # small broadcast
            assert not require_response
            get_conn = self.incoming_connections.get
            for conn_id in controller.group:
                conn = get_conn(conn_id)
                if conn:
                    conn.send(packet_buffer)
        else:
            controller.conn.send(packet_buffer)

        if not require_response:
            return

        self.stub_response[meta.service_method] = response_class
        async_result = AsyncResult()
        controller.conn.transmissions[transmission_id] = async_result
        return async_result.get()

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

    def connection_handler(self, conn):
        header_length, max_packet_length = HEADER_LENGTH, self.MAX_PACKET_LENGTH
        read, unpack_packet = conn.read, Controller.unpack_packet
        tasks_queue, handle_response = Queue(), self.handle_response
        greenlet_pool.spawn(self.sequential_worker, tasks_queue)
        callbacks = {
            REQUEST: self.handle_request,
            NOTIFICATION: self.handle_notification,
        }
        new_task = tasks_queue.put
        try:
            while 1:
                header = read(header_length)
                if not header:
                    conn.close(reset=True)
                    break
                parser_type, packet_length, content_length = unpack_header(header)
                if packet_length > max_packet_length:
                    conn.close(PacketTooLarge(packet_length=packet_length))
                    break

                buf = read(packet_length+content_length)
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

        if service_method not in self.service_methods:
            controller.SetFailed(RPCNotExist(service_method=service_method))
            conn.send(controller.pack_packet())
            return

        method, request_class, response_class = self.service_methods[service_method]
        def send_response(response):
            assert response, 'rpc does not require a response of None'
            assert isinstance(response, response_class)
            controller.pack_content(response)
            conn.send(controller.pack_packet())

        request = controller.unpack_content(request_class)
        try:
            method(controller, request, send_response)
        except BaseError as ex:
            controller.SetFailed(ex)
            conn.send(controller.pack_packet())

    def handle_notification(self, conn, controller):
        service_method = controller.meta.service_method
        if service_method not in self.service_methods:
            # failed silently when handle_notification
            return

        method, request_class, response_class = self.service_methods[service_method]
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
