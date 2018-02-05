from google.protobuf.message import DecodeError

from pymaid.error import BaseEx, Error, RpcError, ErrorManager

from . import pack_header
from .pymaid_pb2 import Void, ErrorMessage, Controller as PBC

__all__ = ['Listener']


class Listener(object):

    def __init__(self):
        self.service_methods = {}

    def append_service(self, service):
        service_methods = self.service_methods
        for method in service.DESCRIPTOR.methods:
            impl_method = getattr(service, method.name)
            if '.<lambda>' in str(impl_method):
                continue
            full_name = method.full_name
            assert full_name not in service_methods
            tuples = (
                impl_method,
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
        meta.service_method = ''

        conn = controller.conn
        rpc = self.service_methods.get(service_method)
        if not rpc:
            meta.is_failed = True
            err = RpcError.RPCNotExist(service_method)
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

        try:
            method(controller, request_class.FromString(content),
                   send_response)
        except BaseEx as ex:
            meta.is_failed = True
            packet = ErrorMessage(code=ex.code, message=ex.message)
            conn.send(b'{}{}{}'.format(
                pack_header(meta.ByteSize(), packet.ByteSize()),
                meta.SerializeToString(), packet.SerializeToString()
            ))
            if isinstance(ex, Error) and conn.close_conn_onerror:
                conn.delay_close(ex)

    def handle_response(self, controller, content):
        meta = controller.meta
        result = controller.conn.transmissions.pop(meta.transmission_id, None)
        if not result:
            # invalid transmission_id, do nothing
            return
        result, response_class = result

        if meta.is_failed:
            try:
                err = ErrorMessage.FromString(content)
            except (DecodeError, ValueError) as ex:
                ex = ex
            else:
                ex = ErrorManager.get_exception(err.code)
                if ex is None:
                    ex = ErrorManager.add_warning(
                        'Unknown%d' % err.code, err.code, err.message
                    )
                ex = ex()
                ex.message = err.message
            result.set_exception(ex)
        else:
            try:
                result.set(response_class.FromString(content))
            except (DecodeError, ValueError) as ex:
                result.set_exception(ex)

    def handle_notification(self, controller, content):
        service_method = controller.meta.service_method
        rpc = self.service_methods.get(service_method)
        if not rpc:
            # failed silently when handle_notification
            return

        method, request_class, response_class = rpc
        try:
            method(controller, request_class.FromString(content),
                   lambda *args, **kwargs: '')
        except BaseEx:
            # failed silently when handle_notification
            pass
