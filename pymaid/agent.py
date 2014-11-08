from pymaid.controller import Controller


class ServiceAgent(object):

    __slot__ = ['stub']

    def __init__(self, stub, conn):
        self.stub = stub
        self.conn = conn
        self._descriptor = stub.GetDescriptor()

    def get_method_by_name(self, name):
        return self._descriptor.FindMethodByName(name)

    def get_request_class(self, method):
        return self.stub.GetRequestClass(method)

    def __dir__(self):
        return dir(self.stub)

    def __getattr__(self, name):
        method_descriptor = self.get_method_by_name(name)
        if not method_descriptor:
            return object.__getattr__(self, name)

        def rpc(controller=None, request=None, done=None, conn=None, **kwargs):
            if controller is None:
                controller = Controller()
                assert conn or self.conn
                controller.conn = conn or self.conn

            if request is None:
                request_class = self.get_request_class(method_descriptor)
                if kwargs:
                    request = request_class(**kwargs)
                else:
                    request = request_class()

            method = getattr(self.stub, name)
            return method(controller, request, done)
        return rpc
