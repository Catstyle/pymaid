from typing import Sequence

from google.protobuf.descriptor_pb2 import MethodDescriptorProto
from google.protobuf.service_reflection import GeneratedServiceType

from pymaid.utils.logger import logger_wrapper

from .method import UnaryUnaryMethod, UnaryStreamMethod
from .method import StreamUnaryMethod, StreamStreamMethod
from .method import UnaryUnaryMethodStub, UnaryStreamMethodStub
from .method import StreamUnaryMethodStub, StreamStreamMethodStub


class ServiceRepository:

    def __init__(self, services: Sequence[GeneratedServiceType] = []):
        self.service_methods = {}
        for service in services:
            self.append_service(service)

    def append_service(self, service: GeneratedServiceType):
        service_methods = self.service_methods
        for method in service.DESCRIPTOR.methods:
            method_impl = getattr(service, method.name)
            if '.<lambda>' in str(method_impl):
                continue

            mdp = MethodDescriptorProto()
            method.CopyToProto(mdp)
            if not mdp.client_streaming and not mdp.server_streaming:
                method_class = UnaryUnaryMethod
            elif not mdp.client_streaming and mdp.server_streaming:
                method_class = UnaryStreamMethod
            elif mdp.client_streaming and not mdp.server_streaming:
                method_class = StreamUnaryMethod
            elif mdp.client_streaming and mdp.server_streaming:
                method_class = StreamStreamMethod
            else:
                assert False, 'should be one of above'

            full_name = method.full_name
            assert full_name not in service_methods
            method_ins = method_class(
                full_name,
                method_impl,
                service.GetRequestClass(method),
                service.GetResponseClass(method)
            )
            service_methods[full_name] = method_ins
            # js/lua pb lib will format as '.service.method'
            service_methods['.' + full_name] = method_ins

    def get_service_method(self, name):
        return self.service_methods.get(name)


@logger_wrapper
class ServiceStub:

    def __init__(self, stub):
        self.methods = {}
        self.build_method_stub(stub)

    def build_method_stub(self, stub):
        self.stub = stub
        methods = self.methods
        for method in stub.DESCRIPTOR.methods:
            mdp = MethodDescriptorProto()
            method.CopyToProto(mdp)
            if not mdp.client_streaming and not mdp.server_streaming:
                method_class = UnaryUnaryMethodStub
            elif not mdp.client_streaming and mdp.server_streaming:
                method_class = UnaryStreamMethodStub
            elif mdp.client_streaming and not mdp.server_streaming:
                method_class = StreamUnaryMethodStub
            elif mdp.client_streaming and mdp.server_streaming:
                method_class = StreamStreamMethodStub
            else:
                assert False, 'should be one of above'
            method_stub = method_class(
                method.full_name,
                stub.GetRequestClass(method),
                stub.GetResponseClass(method)
            )
            setattr(self, method.name, method_stub)
            methods[method.full_name] = method_stub
