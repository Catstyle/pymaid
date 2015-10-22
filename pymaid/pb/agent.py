from pymaid.pb.controller import Controller
from pymaid.parser import DEFAULT_PARSER


class ServiceAgent(object):

    def __init__(self, stub, conn=None, profiling=False):
        self.conn, self.controller = conn, Controller()
        self.profiling, self.service_methods = profiling, {}
        self.CallMethod = stub.rpc_channel.CallMethod
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
        def rpc(request=None, controller=None, callback=None, conn=None,
                broadcast=False, group=None, parser_type=DEFAULT_PARSER,
                **kwargs):
            if not controller:
                controller = self.controller
                controller.Reset()

            controller.broadcast, controller.group = broadcast, group
            controller.parser_type = parser_type
            if not (broadcast or group is not None):
                assert conn or self.conn
                controller.conn = conn or self.conn

            return self.CallMethod(
                method, controller, request or request_class(**kwargs),
                response_class, callback
            )
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
