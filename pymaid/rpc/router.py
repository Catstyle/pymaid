from typing import Coroutine, List, Sequence

from pymaid.utils.logger import logger_wrapper

from .types import RouterType, ServiceType


class Router:

    def __init__(
        self,
        *,
        services: Sequence[ServiceType] = [],
        routers: Sequence[RouterType] = [],
    ):
        self.routes = {}
        for service in services:
            self.include_service(service)
        for router in routers:
            self.include_router(router)

    def include_router(self, router: RouterType):
        self.routes.update(router.routes)

    def include_service(self, service: ServiceType):
        routes = self.routes
        for method in self.get_service_methods(service):
            assert method.full_name not in routes
            routes[method.full_name] = method
            # js/lua pb lib will format as '.service.method'
            routes['.' + method.full_name] = method

    def include_services(self, services: Sequence[ServiceType]):
        for service in services:
            self.include_service(service)

    def get_service_methods(self, service: ServiceType):
        pass

    def get_route(self, name):
        return self.routes.get(name)

    def feed_messages(self, messages) -> List[Coroutine]:
        raise NotImplementedError('feed_messages')


@logger_wrapper(name='pymaid.RouterStub')
class RouterStub:

    def __init__(self, stub):
        self.stub = stub
        self.routes = {}
        self.build_method_stub()

    def build_method_stub(self):
        routes = self.routes
        for method_stub in self.get_router_stubs(self.stub):
            setattr(self, method_stub.name, method_stub)
            routes[method_stub.full_name] = method_stub

    def get_router_stubs(self):
        raise NotImplementedError('get_router_stubs')
