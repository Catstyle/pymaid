from functools import partial
from typing import Optional, TypeVar

from google.protobuf.message import DecodeError
from ujson import loads

from pymaid.core import current_task, get_running_loop
from pymaid.core import Future, Queue, TimeoutError
from pymaid.error import ErrorManager
from pymaid.utils.logger import logger_wrapper

from .channel import ConnectionType
from .error import RPCError
from .method import MethodStub
from .pymaid_pb2 import ErrorMessage, Controller as Meta

__all__ = ['Controller', 'InboundController', 'OutboundController']


@logger_wrapper
class Controller:

    def __init__(
        self,
        *,
        conn: ConnectionType,
        transmission_id: int,
        method: MethodStub,
        timeout: Optional[float] = None,
    ):
        self.conn = conn
        self.method = method
        self.timeout = timeout
        self.timer = None

        # even within the same streaming rpc, the transmission will stay the same
        self.transmission_id = transmission_id
        self.is_cancelled = False
        self.is_closed = False
        self.error = None

        # self.meta = Meta(
        #     transmission_id=self.transmission_id,
        #     packet_flags=self.method.flags,
        # )

        self.task = current_task()
        self.init()

    def init(self):
        pass

    def close(self, reason: Optional[Exception] = None):
        if self.is_closed:
            return
        self.is_closed = True
        self.conn.release_controller(self.transmission_id)
        self.conn = None
        if self.timer:
            self.timer.cancel()
            self.timer = None
        self.task = None
        self.method = None

    def cancel(self, error: Optional[Exception] = None):
        self.logger.debug(f'[Controller|{self}] cancelled with [error|{error}]')
        self.error = error
        self.is_cancelled = True
        self.task.cancel()
        self.close(error)

    async def __aenter__(self):
        if self.is_closed:
            raise RuntimeError('cannot reuse closed controller')
        if self.timeout is not None:
            self.timer = get_running_loop().call_later(
                self.timeout,
                partial(self.cancel, TimeoutError('controller action timeout')),
            )
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        self.close(exc_value)
        if exc_value:
            raise exc_value
        if self.error:
            ex = self.error
            del self.error
            raise ex

    def __aiter__(self):
        return self

    async def __anext__(self):
        if m := await self.recv_message():
            return m
        raise StopAsyncIteration()

    def __repr__(self):
        return f'<{self.__class__.__name__} transmission_id={self.transmission_id}'


class InboundController(Controller):

    def send_message(self, response=None, *, end: bool = False, **kwargs):
        if not self.method.require_response:
            # do not send_message when not require_response
            return
        self.conn.send_message(
            Meta(
                transmission_id=self.transmission_id,
                packet_type=Meta.RESPONSE,
                packet_flags=self.method.flags,
            ),
            response or self.response_class(**kwargs),
        )


class OutboundController(Controller):

    def init(self):
        self.result = Future()

    def feed_message(self, meta, payload):
        ''' received response meta from transport layer '''
        assert meta.packet_type == Meta.RESPONSE, f'invalid {meta.packet_type=}'
        if meta.is_failed:
            try:
                err = ErrorMessage.FromString(payload)
            except (DecodeError, ValueError) as ex:
                ex = ex
            else:
                ex = ErrorManager.assemble(
                    err.code, err.message, err.data and loads(err.data) or {}
                )
            self.result.set_exception(ex)
        elif payload:
            try:
                self.result.set_result(self.method.response_class.FromString(payload))
            except (DecodeError, ValueError) as ex:
                self.result.set_exception(ex)

    def send_message(self, request=None, *, end: bool = False, **kwargs):
        self.conn.send_message(
            Meta(
                transmission_id=self.transmission_id,
                service_method=self.method.name,
                packet_type=Meta.REQUEST,
                packet_flags=self.method.flags,
            ),
            request or self.method.request_class(**kwargs)
        )

        if not self.method.require_response:
            self.result.set_result(None)

    async def recv_message(self):
        ''' called from app logic to wait for response '''
        return await self.result


class InboundStreamingController(Controller):

    def init(self):
        self.request_queue = Queue()
        self.request_received_count = 0
        self.request_fed_count = 0

    def close(self, reason: Optional[Exception] = None):
        super().close(reason)
        self.request_queue = None

    def feed_message(self, meta, payload):
        ''' received request meta from transport layer '''
        assert meta.packet_type == Meta.REQUEST, f'invalid {meta.packet_type=}'
        if self.request_fed_count > 0 and not self.method.client_streaming:
            raise RPCError.MultipleRequestForUnaryMethod(
                data={
                    'service_method': self.method.name,
                    'transmission_id': self.transmission_id,
                }
            )
        if payload:
            self.request_queue.put_nowait(
                self.method.request_class.FromString(payload)
            )
        if meta.packet_flags & Meta.PacketFlag.END_STREAM:
            self.request_queue.put_nowait(None)
        self.request_fed_count += 1

    def send_message(self, response=None, *, end: bool = False, **kwargs):
        if not self.method.require_response:
            # do not send_message when not require_response
            return
        flags = self.method.flags
        if end:
            flags |= Meta.PacketFlag.END_STREAM
        self.conn.send_message(
            Meta(
                transmission_id=self.transmission_id,
                packet_type=Meta.RESPONSE,
                packet_flags=flags,
            ),
            response or self.response_class(**kwargs),
        )

    async def recv_message(self):
        if self.request_received_count > 0 and not self.method.client_streaming:
            raise RPCError.RPCRequestReceived(
                data={
                    'service_method': self.method.name,
                    'transmission_id': self.transmission_id,
                }
            )
        req = await self.request_queue.get()
        self.request_queue.task_done()
        self.request_received_count += 1
        return req


class OutboundStreamingController(Controller):

    def init(self):
        self.request_sent_count = 0
        self.response_queue = Queue()
        self.response_received_count = 0
        self.response_fed_count = 0

    def close(self, reason: Optional[Exception] = None):
        super().close(reason)
        self.response_queue = None

    def feed_message(self, meta, payload):
        ''' received response meta from transport layer '''
        assert meta.packet_type == Meta.RESPONSE, f'invalid {meta.packet_type=}'
        if self.response_fed_count > 0 and not self.method.server_streaming:
            raise RPCError.MultipleResponseForUnaryMethod(
                data={
                    'service_method': self.method.name,
                    'transmission_id': self.transmission_id,
                }
            )
        message = None
        if meta.is_failed:
            message = ErrorMessage.FromString(payload)
        elif payload:
            message = self.method.response_class.FromString(payload)
        if message:
            self.response_queue.put_nowait(message)
        if meta.packet_flags & Meta.PacketFlag.END_STREAM:
            self.response_queue.put_nowait(None)
        self.response_fed_count += 1

    def send_message(self, request=None, *, end: bool = False, **kwargs):
        if self.request_sent_count > 0 and not self.method.client_streaming:
            raise RPCError.RPCRequestSent(
                data={
                    'service_method': self.method.name,
                    'transmission_id': self.transmission_id,
                }
            )

        flags = self.method.flags
        if end:
            flags |= Meta.PacketFlag.END_STREAM
        meta = Meta(
            transmission_id=self.transmission_id,
            service_method=self.method.name,
            packet_type=Meta.REQUEST,
            packet_flags=flags,
        )

        self.conn.send_message(
            meta, request or self.method.request_class(**kwargs)
        )
        self.request_sent_count += 1

        if not self.method.require_response:
            self.response_queue.put_nowait(None)

    async def recv_message(self):
        ''' called from app logic to wait for response '''
        assert self.request_sent_count, 'should call send_message first'
        if self.response_received_count > 0 and not self.method.server_streaming:
            raise RPCError.RPCResponseReceived(
                data={
                    'service_method': self.method.name,
                    'transmission_id': self.transmission_id,
                }
            )
        resp = await self.response_queue.get()
        self.response_queue.task_done()
        self.response_received_count += 1
        if isinstance(resp, ErrorMessage):
            raise resp
        return resp


C = TypeVar('Controller', bound=Controller)
