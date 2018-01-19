from gevent.event import AsyncResult

from pymaid.utils.functional import Broadcaster
from pymaid.utils.logger import pymaid_logger_wrapper, trace_stub

from . import pack_header
from .pymaid_pb2 import Void, Controller


class Sender(object):

    def __init__(self, target):
        self.target = target

    def send(self, meta, request):
        self.target.send(b''.join([
            pack_header(meta.ByteSize(), request.ByteSize()),
            meta.SerializeToString(), request.SerializeToString()
        ]))


@pymaid_logger_wrapper
class ServiceStub(object):

    def __init__(self, stub, conn=None):
        self.stub, self.meta = stub, Controller()
        self.conn = conn
        self.service_stubs = {}
        self._bind_stub()

    def _bind_stub(self):
        stub, rpc_stub = self.stub, self._build_rpc_stub
        service_stubs = self.service_stubs
        for method in stub.DESCRIPTOR.methods:
            rpc = rpc_stub(
                method.full_name,
                stub.GetRequestClass(method),
                stub.GetResponseClass(method)
            )
            setattr(self, method.name, rpc)
            service_stubs[method.full_name] = rpc

    def _build_rpc_stub(self, service_method, request_class, response_class):
        if not issubclass(response_class, Void):
            packet_type, require_response = Controller.REQUEST, True
        else:
            packet_type, require_response = Controller.NOTIFICATION, False
        StubManager.request_class[service_method] = request_class
        StubManager.response_class[service_method] = response_class

        @trace_stub(stub=self, stub_name=service_method.split('.')[-1],
                    request_name=request_class.__name__)
        def rpc(request=None, conn=None, broadcaster=None, **kwargs):
            request = request or request_class(**kwargs)

            meta = self.meta
            meta.Clear()
            meta.service_method = service_method
            meta.packet_type = packet_type
            if broadcaster is not None:
                if not isinstance(broadcaster, Broadcaster):
                    content = b''.join([
                        pack_header(meta.ByteSize(), request.ByteSize()),
                        meta.SerializeToString(), request.SerializeToString()
                    ])
                    for sender in broadcaster:
                        sender.send(content)
                else:
                    for sender in broadcaster:
                        sender.send(meta, request)
            else:
                conn = conn or self.conn
                assert conn, conn
                if require_response:
                    tid = meta.transmission_id = conn.transmission_id
                    conn.transmission_id += 1
                conn.send(b''.join([
                    pack_header(meta.ByteSize(), request.ByteSize()),
                    meta.SerializeToString(), request.SerializeToString()
                ]))

                if not require_response:
                    return

                async_result = AsyncResult()
                conn.transmissions[tid] = (async_result, response_class)

                def cleanup(result):
                    conn.transmissions.pop(tid, None)
                cleanup.auto_unlink = True
                async_result.rawlink(cleanup)

                return async_result
        return rpc

    def close(self):
        self.stub = self.meta = self.conn = None


class StubManager(object):

    request_class = {}
    response_class = {}

    def __init__(self, conn=None):
        self.conn = conn
        self._stubs = {}
        self._service_methods = {}

    def add_stub(self, name, stub):
        assert name not in self._stubs, (name, self._stubs.keys())
        self._stubs[name] = stub
        stub.conn = stub.conn or self.conn
        stub.name = name
        setattr(self, name, stub)
        self._service_stubs.update(stub.service_stubs)

    def remove_stub(self, name):
        assert name in self._stubs, (name, self._stubs.keys())
        stub = self._stubs.pop(name, None)
        delattr(self, name)
        for service_stub in stub.service_stubs:
            self._service_stubs.pop(service_stub, None)
        stub.close()
