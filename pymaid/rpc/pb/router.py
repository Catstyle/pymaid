from google.protobuf.descriptor_pb2 import MethodDescriptorProto
from google.protobuf.service_reflection import GeneratedServiceType

from pymaid.rpc.method import UnaryUnaryMethod, UnaryStreamMethod
from pymaid.rpc.method import StreamUnaryMethod, StreamStreamMethod
from pymaid.rpc.method import UnaryUnaryMethodStub, UnaryStreamMethodStub
from pymaid.rpc.method import StreamUnaryMethodStub, StreamStreamMethodStub
from pymaid.rpc.router import Router, RouterStub

from .pymaid_pb2 import Context as Meta, Void


class PBRouter(Router):

    def get_service_methods(self, service: GeneratedServiceType):
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

            request_class = service.GetRequestClass(method)
            response_class = service.GetResponseClass(method)
            method_ins = method_class(
                method.name,
                method.full_name,
                method_impl,
                request_class,
                response_class,
                options={
                    'flags': Meta.PacketFlag.NULL,
                    'void_request': issubclass(request_class, Void),
                    'void_response': issubclass(response_class, Void),
                },
            )
            yield method_ins


class PBRouterStub(RouterStub):

    def get_router_stubs(self, stub):
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

            request_class = stub.GetRequestClass(method)
            response_class = stub.GetResponseClass(method)
            method_stub = method_class(
                method.name,
                method.full_name,
                request_class,
                response_class,
                options={
                    'flags': Meta.PacketFlag.NULL,
                    'void_request': issubclass(request_class, Void),
                    'void_response': issubclass(response_class, Void),
                },
            )
            yield method_stub
