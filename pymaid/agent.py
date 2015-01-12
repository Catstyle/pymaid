from pymaid.controller import Controller


class ServiceAgent(object):

    __slots__ = [
        'stub', 'conn', 'controller', 'get_method_by_name', 'get_request_class',
        'profiling',
    ]

    def __init__(self, stub, conn, profiling=False):
        self.stub, self.conn, self.controller = stub, conn, Controller()
        self.get_method_by_name = stub.GetDescriptor().FindMethodByName
        self.get_request_class = stub.GetRequestClass
        self.profiling = profiling

    def close(self):
        self.stub, self.conn, self.controller = None, None, None
        self.get_method_by_name, self.get_request_class = None, None

    def print_summary(slef):
        from pymaid.utils.profiler import default
        default.print_summary()

    def __dir__(self):
        return dir(self.stub)

    def __getattr__(self, name):
        method_descriptor = self.get_method_by_name(name)
        if not method_descriptor:
            return object.__getattr__(self, name)

        def rpc(controller=None, request=None, done=None, conn=None, **kwargs):
            if controller is None:
                controller = self.controller
                controller.Reset()
                assert conn or self.conn
                controller.conn = conn or self.conn

            if request is None:
                request_class = self.get_request_class(method_descriptor)
                request = request_class(**kwargs)

            method = getattr(self.stub, name)
            if self.profiling:
                from pymaid.utils.profiler import profiling
                method = profiling(name)(method)
            return method(controller, request, done)
        return rpc
