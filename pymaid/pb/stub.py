from gevent.event import AsyncResult

from pymaid.parser import DEFAULT_PARSER, pack
from pymaid.pb.pymaid_pb2 import Void, Controller

REQUEST = Controller.REQUEST
RESPONSE = Controller.RESPONSE
NOTIFICATION = Controller.NOTIFICATION


class ServiceStub(object):

    def __init__(self, stub, conn=None):
        self.stub, self.conn, self.meta = stub, conn, Controller()
        self._bind_stub()

    def _bind_stub(self):
        stub, rpc_stub = self.stub, self._build_rpc_stub
        for method in stub.DESCRIPTOR.methods:
            setattr(self, method.name, rpc_stub(
                method.full_name,
                stub.GetRequestClass(method),
                stub.GetResponseClass(method)
            ))

    def _build_rpc_stub(self, service_method, request_class, response_class):
        if not issubclass(response_class, Void):
            packet_type, require_response = REQUEST, True
        else:
            packet_type, require_response = NOTIFICATION, False
        StubManager.request_class[service_method] = response_class
        StubManager.response_class[service_method] = response_class
        def rpc(request=None, conn=None, connections=None,
                parser_type=DEFAULT_PARSER, **kwargs):
            request = request or request_class(**kwargs)

            meta = self.meta
            meta.Clear()
            meta.service_method = service_method
            meta.packet_type = packet_type
            if connections:
                packet_buffer = pack(meta, request, parser_type)
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

                async_result = AsyncResult()
                conn.transmissions[meta.transmission_id] = async_result
                return async_result.get()
        return rpc

    def close(self):
        self.stub, self.conn, self.meta = None, None, None


class StubManager(object):

    request_class = {}
    response_class = {}

    def __init__(self, conn=None):
        self.conn = conn
        self._stubs = {}

    def bind(self, conn):
        self.conn = conn
        for stub in self._stubs.values():
            stub.conn = conn

    def add_stub(self, name, stub):
        assert name not in self._stubs, (name, self._stubs.keys())
        self._stubs[name] = stub
        stub.conn = stub.conn or self.conn
        stub.name = name
        setattr(self, name, stub)

    def remove_stub(self, name):
        assert name in self._stubs, (name, self._stubs.keys())
        stub = self._stubs.pop(name, None)
        delattr(self, name)
        stub.close()
