from pymaid.controller import Controller
from pymaid.parser import DEFAULT_PARSER


class ServiceAgent(object):

    def __init__(self, stub, conn=None, profiling=False):
        self.conn, self.controller = conn, Controller()
        self.profiling, self.service_methods = profiling, {}
        self.CallMethod = stub.rpc_channel.CallMethod
        self._bind_stub(stub)
        if profiling:
            from pymaid.utils.profiler import profiler
            profiler.enable_all()

    def _bind_stub(self, stub):
        self.stub, service_methods = stub, self.service_methods
        for method in stub.DESCRIPTOR.methods:
            request_class = stub.GetRequestClass(method)
            response_class = stub.GetResponseClass(method)
            if self.profiling:
                from pymaid.utils.profiler import profiler
                method = profiler.profile(method)
            service_methods[method.name] = method, request_class, response_class

    def close(self):
        self.stub, self.conn, self.controller = None, None, None
        self.service_methods.clear()

    def print_summary(slef):
        from pymaid.utils.profiler import profiler
        profiler.print_stats()

    def __dir__(self):
        return dir(self.stub)

    def __getattr__(self, name):
        if name not in self.service_methods:
            return object.__getattr__(self, name)
        method, request_class, response_class = self.service_methods[name]

        def rpc(request=None, controller=None, callback=None, conn=None,
                broadcast=False, group=None, parser_type=DEFAULT_PARSER,
                **kwargs):
            if not controller:
                controller = self.controller
                controller.Reset()

            controller.broadcast, controller.group = broadcast, group
            controller.parser_type = parser_type
            if not (broadcast or group):
                assert conn or self.conn
                controller.conn = conn or self.conn

            if not request:
                assert request_class
                request = request_class(**kwargs)

            return self.CallMethod(
                method, controller, request, response_class, callback
            )
        return rpc
