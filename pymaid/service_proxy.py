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

        def rpc(controller=None, request=None, conn=None, wide=False,
                group=None, **kwargs):
            controller, done = controller or Controller(), None
            if not request:
                request_class = self.stub.GetRequestClass(method_descriptor)
                if kwargs:
                    request = request_class(**kwargs)
                else:
                    request = request_class()

            assert conn or wide or group, 'must specified one way to go'
            if conn:
                controller.conn = conn
            elif wide:
                controller.wide = wide
            else:
                assert isinstance(group, (tuple, list)), \
                        'group should be a list of conn id being used to send data, got "%s"' % type(group)
                controller.group = group

            method = getattr(self.stub, name)
            return method(controller, request, done)
        return rpc
