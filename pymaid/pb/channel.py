__all__ = ['PBChannel']

import six

from gevent.event import AsyncResult

from google.protobuf.message import DecodeError

from pymaid.channel import Channel
from pymaid.parser import REQUEST, RESPONSE, NOTIFICATION
from pymaid.error import BaseError, BaseMeta, ServiceNotExist, MethodNotExist
from pymaid.utils import pymaid_logger_wrapper
from pymaid.pb.pymaid_pb2 import Void, ErrorMessage

range = six.moves.range


@pymaid_logger_wrapper
class PBChannel(Channel):

    def __init__(self, loop=None):
        super(PBChannel, self).__init__(loop)

        self.services = {}
        self.service_method = {}
        self.request_response = {}
        self.stub_response = {}

    def CallMethod(self, method, controller, request, response_class, callback):
        meta = controller.meta
        meta.service_name = method.containing_service.full_name
        meta.method_name = method.name
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
            for conn in self._income_connections.values():
                conn.send(packet_buffer)
        elif controller.group:
            # small broadcast
            assert not require_response
            get_conn = self.get_income_connection
            for conn_id in controller.group:
                conn = get_conn(conn_id)
                if conn:
                    conn.send(packet_buffer)
        else:
            controller.conn.send(packet_buffer)

        if not require_response:
            return

        service_method = meta.service_name + meta.method_name
        self.stub_response.setdefault(service_method, response_class)
        async_result = AsyncResult()
        controller.conn.transmissions[transmission_id] = async_result
        return async_result.get()

    def append_service(self, service):
        assert service.DESCRIPTOR.full_name not in self.services
        self.services[service.DESCRIPTOR.full_name] = service

    def connection_closed(self, conn, reason=None):
        if not conn.server_side:
            for async_result in conn.transmissions.values():
                # we should not reach here with async_result left
                # that should be an exception
                async_result.set_exception(reason)
            conn.transmissions.clear()

    def get_service_method(self, meta):
        service_name, method_name = meta.service_name, meta.method_name
        service_method = service_name + method_name
        if service_method in self.service_method:
            return self.service_method[service_method]

        if service_name not in self.services:
            raise ServiceNotExist(service_name=service_name)

        service = self.services[service_name]
        method = service.DESCRIPTOR.FindMethodByName(method_name)
        if not method:
            raise MethodNotExist(service_name=service_name, method_name=method_name)

        request_class = service.GetRequestClass(method)
        response_class = service.GetResponseClass(method)
        self.service_method[service_method] = service, method
        self.request_response[service_method] = request_class, response_class
        return service, method

    def get_request_response(self, meta):
        service_name, method_name = meta.service_name, meta.method_name
        service_method = service_name + method_name
        if service_method not in self.request_response:
            self.get_service_method(meta)
        return self.request_response[service_method]

    def get_stub_response_class(self, meta):
        return self.stub_response[meta.service_name + meta.method_name]

    def handle_request(self, conn, controller):
        meta = controller.meta
        meta.packet_type = RESPONSE

        try:
            service, method = self.get_service_method(meta)
        except (ServiceNotExist, MethodNotExist) as ex:
            controller.SetFailed(ex)
            conn.send(controller.pack_packet())
            return

        request_class, response_class = self.get_request_response(meta)
        def send_response(response):
            assert response, 'rpc does not require a response of None'
            assert isinstance(response, response_class)
            controller.pack_content(response)
            conn.send(controller.pack_packet())

        request = controller.unpack_content(request_class)
        try:
            service.CallMethod(method, controller, request, send_response)
        except BaseError as ex:
            controller.SetFailed(ex)
            conn.send(controller.pack_packet())

    def handle_notification(self, conn, controller):
        meta = controller.meta
        try:
            service, method = self.get_service_method(meta)
        except (ServiceNotExist, MethodNotExist):
            # failed silently when handle_notification
            return

        request_class, response_class = self.get_request_response(meta)
        request = controller.unpack_content(request_class)
        try:
            service.CallMethod(method, controller, request, None)
        except BaseError:
            # failed silently when handle_notification
            pass

    def handle_response(self, controller):
        transmission_id = controller.meta.transmission_id
        assert transmission_id in self.transmissions
        async_result = self.transmissions.pop(transmission_id)

        if controller.Failed():
            error_message = controller.unpack_content(ErrorMessage)
            ex = BaseMeta.get_by_code(error_message.error_code)()
            ex.message = error_message.error_message
            async_result.set_exception(ex)
        else:
            response_cls = self.channel.get_stub_response_class(controller.meta)
            try:
                async_result.set(controller.unpack_content(response_cls))
            except DecodeError as ex:
                async_result.set_exception(ex)

