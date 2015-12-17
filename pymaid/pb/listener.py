__all__ = ['Listener']


class Listener(object):

    def __init__(self):
        self.service_methods = {}

    def append_service(self, service):
        service_methods = self.service_methods
        for method in service.DESCRIPTOR.methods:
            full_name = method.full_name
            assert full_name not in service_methods
            tuples = (
                getattr(service, method.name),
                service.GetRequestClass(method),
                service.GetResponseClass(method)
            )
            service_methods[full_name] = tuples
            # js/lua pb lib will format as '.service.method'
            service_methods['.'+full_name] = tuples
