from pymaid.controller import Controller
from pymaid.parser import DEFAULT_PARSER


class ServiceAgent(object):

    def __init__(self, stub, conn=None, profiling=False):
        self.stub, self.conn, self.controller = stub, conn, Controller()
        self.profiling, self.methods = profiling, {}
        self.CallMethod = stub.rpc_channel.CallMethod
        if profiling:
            from pymaid.utils.profiler import profiler
            profiler.enable_all()

    def close(self):
        self.stub, self.conn, self.controller = None, None, None
        self.methods.clear()

    def get_method(self, name):
        if name in self.methods:
            return self.methods[name]

        method_descriptor = self.stub.DESCRIPTOR.FindMethodByName(name)
        request_class, response_class = None, None
        if method_descriptor:
            request_class = self.stub.GetRequestClass(method_descriptor)
            response_class = self.stub.GetResponseClass(method_descriptor)
            if self.profiling:
                from pymaid.utils.profiler import profiler
                method_descriptor = profiler.profile(method_descriptor)
            self.methods[name] = method_descriptor, request_class, response_class
        return method_descriptor, request_class, response_class

    def print_summary(slef):
        from pymaid.utils.profiler import profiler
        profiler.print_stats()

    def __dir__(self):
        return dir(self.stub)

    def __getattr__(self, name):
        method_descriptor, request_class, response_class = self.get_method(name)
        if not method_descriptor:
            return object.__getattr__(self, name)

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
                method_descriptor, controller, request, response_class, callback
            )
        return rpc
