from gevent.event import AsyncResult
from six import itervalues

from pymaid.parser import DEFAULT_PARSER
from pymaid.pb.channel import pack
from pymaid.pb.controller import Controller
from pymaid.pb.pymaid_pb2 import Void, Controller as PBC

REQUEST, RESPONSE, NOTIFICATION = PBC.REQUEST, PBC.RESPONSE, PBC.NOTIFICATION


class ServiceAgent(object):

    def __init__(self, stub, conn=None, profiling=False):
        self.conn, self.controller = conn, Controller()
        self.profiling, self.service_methods = profiling, {}
        self._bind_stub(stub)
        self._get_rpc = self.service_methods.get

    def _bind_stub(self, stub):
        self.stub, service_methods = stub, self.service_methods
        rpc_stub = self._build_rpc_stub
        for method in stub.DESCRIPTOR.methods:
            request_class = stub.GetRequestClass(method)
            response_class = stub.GetResponseClass(method)
            if self.profiling:
                from pymaid.utils.profiler import profiler
                profiler.profile(getattr(stub, method.name))
            service_methods[method.name] = rpc_stub(
                method, request_class, response_class
            )

    def _build_rpc_stub(self, method, request_class, response_class):
        if not issubclass(response_class, Void):
            packet_type, require_response = REQUEST, True
        else:
            packet_type, require_response = NOTIFICATION, False
        def rpc(request=None, controller=None, channel=None, conn=None,
                broadcast=False, group=None, parser_type=DEFAULT_PARSER,
                **kwargs):
            if not controller:
                controller = self.controller
                controller.Reset()
            request = request or request_class(**kwargs)

            meta = controller.meta
            meta.service_method = method.full_name
            meta.packet_type = packet_type
            if broadcast or group:
                assert channel, 'group/broadcast without channel'
                packet_buffer = pack(meta, request, parser_type)
                _connections = channel.connections
                if broadcast:
                    connections = itervalues(_connections)
                else:
                    connections = (
                        _connections[cid] for cid in group if cid in _connections
                    )
                for conn in connections:
                    conn.send(packet_buffer)
            else:
                assert conn or self.conn
                conn = conn or self.conn
                if require_response:
                    meta.transmission_id = conn.transmission_id
                    conn.transmission_id += 1
                packet_buffer = pack(meta, request, parser_type)
                conn.send(packet_buffer)
                
                if not require_response:
                    return

                conn.channel.stub_response[meta.service_method] = response_class
                async_result = AsyncResult()
                conn.transmissions[meta.transmission_id] = async_result
                return async_result.get()
        return rpc

    def close(self):
        self.stub, self.conn, self.controller = None, None, None
        self.service_methods.clear()

    def __dir__(self):
        return dir(self.stub)

    def __getattr__(self, name):
        ret = self._get_rpc(name)
        if not ret:
            raise AttributeError(name)
        return ret
