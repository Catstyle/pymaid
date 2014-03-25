from pymaid.controller import Controller


class ServiceProxy(object):

    __slot__ = ['stub']

    def __init__(self, stub):
        self.stub = stub
        self._descriptor = stub.GetDescriptor()

    def __dir__(self):
        return dir(self.stub)

    def __getattr__(self, name):
        method_descriptor = self._descriptor.FindMethodByName(name)
        if not method_descriptor:
            return object.__getattr__(self, name)

        def rpc(**kwargs):
            controller, done = Controller(), None
            request_class = self.stub.GetRequestClass(method_descriptor)

            if kwargs:
                request = request_class(**kwargs)
            else:
                request = request_class()
            method = getattr(self.stub, name)
            return method(controller, request, done)
        return rpc
