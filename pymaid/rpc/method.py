from abc import ABCMeta, abstractmethod
from typing import AsyncIterable, Callable, Optional, Sequence, Type, Union

from google.protobuf.descriptor_pb2 import MethodDescriptorProto
from google.protobuf.message import Message
from google.protobuf.service_reflection import GeneratedServiceType
from ujson import dumps

from pymaid.error import BaseEx
from pymaid.utils.logger import logger_wrapper

from .channel import ConnectionType
from .pymaid_pb2 import Controller as Meta, ErrorMessage, Void
from .utils import trace_stub


class Method:

    def __init__(
        self,
        name: str,
        method_impl: Callable,
        request_class: Type[Message],
        response_class: Type[Message],
    ):
        self.name = name
        self.method_impl = method_impl
        self.request_class = request_class
        self.response_class = response_class
        self.flags = Meta.PacketFlag.NULL

        if not issubclass(response_class, Void):
            self.require_response = True
        else:
            self.require_response = False

    def open(
        self,
        transmission_id,
        *,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ):
        return conn.new_inbound_controller(
            transmission_id, method=self, timeout=timeout,
        )

    async def __call__(
        self,
        meta: Meta,
        payload: Union[bytes, memoryview],
        *,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ):
        '''method will be handle in new task'''
        try:
            async with self.open(
                meta.transmission_id, conn=conn, timeout=timeout,
            ) as controller:
                await self.method_impl(controller, self.request_class.FromString(payload))
        except BaseEx as exc:
            meta.is_failed = True
            packet = ErrorMessage(code=exc.code, message=exc.message),
            if exc.data:
                packet.data = dumps(exc.data)
            conn.send_message(meta, packet)


class UnaryUnaryMethod(Method):

    client_streaming = False
    server_streaming = False


class UnaryStreamMethod(Method):

    client_streaming = False
    server_streaming = True


class StreamUnaryMethod(Method):

    client_streaming = True
    server_streaming = False


class StreamStreamMethod(Method):

    client_streaming = True
    server_streaming = True


class ServiceRepository:

    def __init__(self, services: Sequence[GeneratedServiceType]):
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


class MethodStub(metaclass=ABCMeta):

    def __init__(
        self,
        name: str,
        request_class: Message,
        response_class: Message
    ):
        self.name = name
        self.request_class = request_class
        self.response_class = response_class
        self.flags = Meta.PacketFlag.NULL

        if not issubclass(response_class, Void):
            self.require_response = True
        else:
            self.require_response = False

    def open(
        self,
        *,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ):
        return conn.new_outbound_controller(method=self, timeout=timeout)

    @abstractmethod
    def __call__(self, request):
        raise NotImplementedError


class UnaryUnaryMethodStub(MethodStub):

    client_streaming = False
    server_streaming = False

    @trace_stub
    async def __call__(
        self,
        request: Message,
        *,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ):
        async with self.open(conn=conn, timeout=timeout) as controller:
            controller.send_message(request)
            return await controller.recv_message()


class UnaryStreamMethodStub(MethodStub):

    client_streaming = False
    server_streaming = True

    @trace_stub
    async def __call__(
        self,
        request: Message,
        *,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ):
        async with self.open(conn=conn, timeout=timeout) as controller:
            controller.send_message(request)
            return [r async for r in controller]


class StreamUnaryMethodStub(MethodStub):

    client_streaming = True
    server_streaming = False

    @trace_stub
    async def __call__(
        self,
        requests: AsyncIterable[Message],
        *,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ):
        async with self.open(conn=conn, timeout=timeout) as controller:
            async for request in requests:
                controller.send_message(request)
            controller.send_message(end=True)
            return await controller.recv_message()


class StreamStreamMethodStub(MethodStub):

    client_streaming = True
    server_streaming = True

    @trace_stub
    async def __call__(
        self,
        requests: AsyncIterable[Message],
        *,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ):
        async with self.open(conn=conn, timeout=timeout) as controller:
            async for request in requests:
                controller.send_message(request)
            controller.send_message(end=True)
            return [r async for r in controller]


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
