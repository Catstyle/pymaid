__all__ = ['PBChannel']

import six
from _socket import error as socket_error

from gevent.queue import Queue
from google.protobuf.message import DecodeError

from pymaid.channel import Channel
from pymaid.error import RpcError, get_ex_by_code
from pymaid.error.base import BaseEx, Error
from pymaid.utils import greenlet_pool, pymaid_logger_wrapper
from pymaid.parser import (
    HEADER_LENGTH, DEFAULT_PARSER, pack_header, pack_packet,
    unpack_packet, unpack_header,
)

from pymaid.pb.controller import Controller
from pymaid.pb.pymaid_pb2 import Void, ErrorMessage, Controller as PBC


range = six.moves.range
REQUEST, RESPONSE, NOTIFICATION = PBC.REQUEST, PBC.RESPONSE, PBC.NOTIFICATION
RPCNotExist, PacketTooLarge = RpcError.RPCNotExist, RpcError.PacketTooLarge


def pack(meta, content=b'', parser_type=DEFAULT_PARSER):
    if not isinstance(content, Void):
        content = pack_packet(content, parser_type)
    else:
        content = str(content)
    meta_content = pack_packet(meta, parser_type)
    return b''.join([
        pack_header(parser_type, len(meta_content), len(content)),
        meta_content, content
    ])


@pymaid_logger_wrapper
class PBChannel(Channel):

    MAX_PACKET_LENGTH = 8 * 1024

    def __init__(self, loop=None):
        super(PBChannel, self).__init__(loop)
        self.services, self.service_methods, self.stub_response = {}, {}, {}
        self._get_rpc = self.service_methods.get

    def _connection_detached(self, conn, reason):
        if not conn.server_side:
            for async_result in conn.transmissions.values():
                # we should not reach here with async_result left
                # that should be an exception
                async_result.set_exception(reason)
            conn.transmissions.clear()
        super(PBChannel, self)._connection_detached(conn, reason)

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

    def connection_handler(self, conn):
        header_length, max_packet_length = HEADER_LENGTH, self.MAX_PACKET_LENGTH
        read = conn.read
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
                header = read(header_length)
                if not header:
                    conn.close(reset=True)
                    break
                parser_type, packet_length, content_length = unpack_header(header)
                if packet_length > max_packet_length:
                    conn.close(PacketTooLarge(packet_length=packet_length))
                    break

                buf = read(packet_length+content_length)
                assert len(buf) == packet_length + content_length
                meta = unpack_packet(buf[:packet_length], PBC, parser_type)
                controller = Controller(meta, parser_type)
                content = buf[packet_length:]
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

    def sequential_worker(self, tasks_queue):
        get_task = tasks_queue.get
        while 1:
            task = get_task()
            if not task:
                break
            callback, controller, content = task
            callback(controller, content)

    def handle_request(self, controller, content):
        meta = controller.meta
        meta.packet_type = RESPONSE
        service_method = meta.service_method

        conn, parser_type = controller.conn, controller.parser_type
        rpc = self._get_rpc(service_method)
        if not rpc:
            controller.SetFailed()
            err = RPCNotExist(service_method=service_method)
            err = ErrorMessage(error_code=err.code, error_message=err.message)
            conn.send(pack(meta, err, parser_type))
            return

        method, request_class, response_class = rpc
        def send_response(response=None, **kwargs):
            if response_class is Void:
                # do not send_response when response_class is Void
                return
            if response is None:
                response = response_class(**kwargs)
            assert isinstance(response, response_class)
            conn.send(pack(meta, response, parser_type))

        request = unpack_packet(content, request_class, parser_type)
        try:
            method(controller, request, send_response)
        except BaseEx as ex:
            controller.SetFailed()
            err = ErrorMessage(error_code=ex.code, error_message=ex.message)
            conn.send(pack(meta, err, parser_type))
            if isinstance(ex, Error):
                conn.delay_close(ex)

    def handle_notification(self, controller, content):
        service_method = controller.meta.service_method
        rpc = self._get_rpc(service_method)
        if not rpc:
            # failed silently when handle_notification
            return

        method, request_class, response_class = rpc
        request = unpack_packet(content, request_class, controller.parser_type)
        try:
            method(controller, request, lambda *args, **kwargs: '')
        except BaseEx:
            # failed silently when handle_notification
            pass

    def handle_response(self, controller, content):
        conn = controller.conn
        transmission_id = controller.meta.transmission_id
        assert transmission_id in conn.transmissions, (transmission_id, conn.transmissions)
        async_result = conn.transmissions.pop(transmission_id)

        parser_type = controller.parser_type
        if controller.Failed():
            error_message = unpack_packet(content, ErrorMessage, parser_type)
            ex = get_ex_by_code(error_message.error_code)()
            ex.message = error_message.error_message
            async_result.set_exception(ex)
        else:
            response_cls = self.stub_response[controller.meta.service_method]
            try:
                async_result.set(unpack_packet(content, response_cls, parser_type))
            except DecodeError as ex:
                async_result.set_exception(ex)
