import abc
from typing import AsyncIterable, Callable, Optional, Type

from .types import ConnectionType, InboundContext, Request, Response


class Method(abc.ABC):

    def __init__(
        self,
        name: str,
        full_name: str,
        method_impl: Callable,
        request_class: Type[Request],
        response_class: Type[Response],
        *,
        options: dict = None,
    ):
        self.name = name
        self.full_name = full_name
        self.method_impl = method_impl
        self.request_class = request_class
        self.response_class = response_class
        self.options = options or {}

    async def __call__(self, context: InboundContext):
        async with context:
            await self.method_impl(context)


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


class MethodStub(metaclass=abc.ABCMeta):

    def __init__(
        self,
        name: str,
        full_name: str,
        request_class: Type[Request],
        response_class: Type[Response],
        *,
        options: dict = None,
    ):
        self.name = name
        self.full_name = full_name
        self.request_class = request_class
        self.response_class = response_class
        self.options = options or {}

    def open(
        self,
        *,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ):
        return conn.handler.new_outbound_context(method=self, timeout=timeout)

    @abc.abstractmethod
    def __call__(
        self,
        request: Request,
        *,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ):
        raise NotImplementedError()


class UnaryUnaryMethodStub(MethodStub):

    client_streaming = False
    server_streaming = False

    async def __call__(
        self,
        request: Request,
        *,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ):
        async with self.open(conn=conn, timeout=timeout) as context:
            await context.send_message(request)
            return await context.recv_message()


class UnaryStreamMethodStub(MethodStub):

    client_streaming = False
    server_streaming = True

    async def __call__(
        self,
        request: Request,
        *,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ):
        async with self.open(conn=conn, timeout=timeout) as context:
            await context.send_message(request)
            async for resp in context:
                yield resp


class StreamUnaryMethodStub(MethodStub):

    client_streaming = True
    server_streaming = False

    async def __call__(
        self,
        requests: AsyncIterable[Request],
        *,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ):
        async with self.open(conn=conn, timeout=timeout) as context:
            async for request in requests:
                await context.send_message(request)
            await context.send_message(end=True)
            return await context.recv_message()


class StreamStreamMethodStub(MethodStub):

    client_streaming = True
    server_streaming = True

    async def __call__(
        self,
        requests: AsyncIterable[Request],
        *,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ):
        async with self.open(conn=conn, timeout=timeout) as context:
            async for request in requests:
                await context.send_message(request)
            await context.send_message(end=True)
            async for resp in context:
                yield resp
