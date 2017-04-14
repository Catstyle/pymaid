from pymaid.error import BaseEx, Error, RpcError

from . import pack_header
from .pymaid_pb2 import Void, ErrorMessage, Controller as PBC

__all__ = ['Listener']


class Listener(object):

    def __init__(self):
        self.service_methods = {}

    def append_service(self, service):
        service_methods = self.service_methods
        for method in service.DESCRIPTOR.methods:
            full_name = method.full_name
            assert full_name not in service_methods
            tuples = (
                getattr(service, method.name),
                service.GetRequestClass(method),
                service.GetResponseClass(method)
            )
            service_methods[full_name] = tuples
            # js/lua pb lib will format as '.service.method'
            service_methods['.' + full_name] = tuples

    def handle_request(self, controller, content):
        meta = controller.meta
        meta.packet_type = PBC.RESPONSE
        service_method = meta.service_method

        conn = controller.conn
        rpc = self.service_methods.get(service_method)
        if not rpc:
            meta.is_failed = True
            err = RpcError.RPCNotExist(service_method=service_method)
            packet = ErrorMessage(code=err.code, message=err.message)
            conn.send(b'{}{}{}'.format(
                pack_header(meta.ByteSize(), packet.ByteSize()),
                meta.SerializeToString(), packet.SerializeToString()
            ))
            return

        method, request_class, response_class = rpc

        def send_response(response=None, **kwargs):
            if response_class is Void:
                # do not send_response when response_class is Void
                return
            packet = response or response_class(**kwargs)
            conn.send(b'{}{}{}'.format(
                pack_header(meta.ByteSize(), packet.ByteSize()),
                meta.SerializeToString(), packet.SerializeToString()
            ))

        request = request_class.FromString(content)
        try:
            method(controller, request, send_response)
        except BaseEx as ex:
            meta.is_failed = True
            packet = ErrorMessage(code=ex.code, message=ex.message)
            conn.send(b'{}{}{}'.format(
                pack_header(meta.ByteSize(), packet.ByteSize()),
                meta.SerializeToString(), packet.SerializeToString()
            ))
            if isinstance(ex, Error) and conn.close_conn_onerror:
                conn.delay_close(ex)

    def handle_notification(self, controller, content):
        service_method = controller.meta.service_method
        rpc = self.service_methods.get(service_method)
        if not rpc:
            # failed silently when handle_notification
            return

        method, request_class, response_class = rpc
        request = request_class.FromString(content)
        try:
            method(controller, request, lambda *args, **kwargs: '')
        except BaseEx:
            # failed silently when handle_notification
            pass
