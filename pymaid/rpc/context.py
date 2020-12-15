from collections import deque
from functools import partial
from typing import Optional, TypeVar, Union

from orjson import loads, dumps

from pymaid.core import get_running_loop
from pymaid.core import Future, TimeoutError
from pymaid.error import BaseEx, ErrorManager
from pymaid.utils.logger import logger_wrapper

from .channel import ConnectionType
from .error import RPCError
from .method import Method, MethodStub
from .pymaid_pb2 import ErrorMessage, Context as Meta, Void

__all__ = ['C', 'Context', 'InboundContext', 'OutboundContext']


@logger_wrapper
class Context:

    def __init__(
        self,
        *,
        conn: ConnectionType,
        transmission_id: int,
        method: Union[Method, MethodStub],
        timeout: Optional[float] = None,
    ):
        self.conn = conn
        self.method = method
        self.timeout_interval = timeout
        self.timer = None
        self.waiter = None

        self.transmission_id = transmission_id
        self.is_cancelled = False
        self.is_closed = False
        self.sent_end_message = False

        self.init()

    def init(self):
        pass

    async def run(self):
        await self.method(self)

    async def close(self, reason: Optional[Exception] = None):
        if self.is_closed:
            return
        self.logger.debug(f'[Context|{self}] closed with [reason|{reason}]')
        self.is_closed = True
        self.conn.release_context(self.transmission_id)
        self.conn = None
        self.method = None
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if self.waiter:
            if reason is None:
                self.waiter.set_result(reason)
            else:
                self.waiter.set_exception(reason)
            self.waiter = None

    async def cancel(self, reason: Optional[Exception] = None):
        self.logger.debug(f'[Context|{self}] cancelled with [error|{reason}]')
        self.is_cancelled = True
        await self.close(reason)

    async def __aenter__(self):
        if self.is_closed:
            raise RuntimeError('cannot reuse closed context')
        if self.timeout_interval is not None:
            self.timer = get_running_loop().call_later(
                self.timeout_interval,
                partial(self.cancel, TimeoutError('context action timeout')),
            )
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        await self.close(exc_value)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if m := await self.recv_message():
            return m
        raise StopAsyncIteration()

    def __repr__(self):
        return (
            f'<{self.__class__.__name__}@{id(self)} '
            f'transmission_id={self.transmission_id}>'
        )


class InboundContext(Context):

    def init(self):
        self.request_queue = deque()
        self.request_received_count = 0
        self.request_fed_count = 0
        self.response_sent_count = 0

    async def close(self, reason: Optional[Exception] = None):
        if self.is_closed:
            return
        if isinstance(reason, BaseEx):
            await self.conn.send_message(
                Meta(
                    transmission_id=self.transmission_id,
                    packet_type=Meta.RESPONSE,
                    packet_flags=self.method.flags | Meta.PacketFlag.END,
                    is_failed=True,
                ),
                ErrorMessage(
                    code=reason.code,
                    message=reason.message,
                    data=dumps(reason.data) if reason.data else '',
                ),
            )
            self.sent_end_message = True
        if self.method.server_streaming and not self.sent_end_message:
            await self.conn.send_message(
                Meta(
                    transmission_id=self.transmission_id,
                    packet_type=Meta.RESPONSE,
                    packet_flags=self.method.flags | Meta.PacketFlag.END,
                ),
                Void(),
            )
        await super().close(reason)

    def feed_message(self, meta, payload):
        '''Received request from transport layer'''
        assert meta.packet_type == Meta.REQUEST, f'invalid {meta.packet_type=}'
        if self.request_fed_count > 0 and not self.method.client_streaming:
            raise RPCError.MultipleRequestForUnaryMethod(
                data={
                    'service_method': self.method.name,
                    'transmission_id': self.transmission_id,
                }
            )
        if payload:
            self.request_queue.append(
                self.method.request_class.FromString(payload)
            )
        if meta.packet_flags & Meta.PacketFlag.END:
            self.request_queue.append(None)
        self.request_fed_count += 1
        if self.waiter and not self.waiter.done():
            self.waiter.set_result(True)

    async def send_message(
        self, response=None, *, end: bool = False, **kwargs
    ):
        '''Send response to transport layer'''
        if not self.method.require_response:
            # do not send_message when not require_response
            return
        if self.response_sent_count > 0 and not self.method.server_streaming:
            raise RPCError.RPCResponseSent(
                data={
                    'service_method': self.method.name,
                    'transmission_id': self.transmission_id,
                }
            )
        flags = self.method.flags
        if end or not self.method.server_streaming:
            flags |= Meta.PacketFlag.END
            self.sent_end_message = True
        await self.conn.send_message(
            Meta(
                transmission_id=self.transmission_id,
                packet_type=Meta.RESPONSE,
                packet_flags=flags
            ),
            response or self.method.response_class(**kwargs),
        )

    async def recv_message(self):
        '''Wait for request from logic layer

        In any cases, this should be called by the same one logic.
        '''
        if (self.request_received_count > 0
                and not self.method.client_streaming):
            raise RPCError.RPCRequestReceived(
                data={
                    'service_method': self.method.name,
                    'transmission_id': self.transmission_id,
                }
            )
        if not self.request_queue:
            assert self.waiter is None, \
                'should not called parallelly at the same time'
            self.waiter = Future()
            try:
                await self.waiter
            finally:
                self.waiter = None
        self.request_received_count += 1
        req = self.request_queue.popleft()
        if isinstance(req, Exception):
            raise req
        return req


class OutboundContext(Context):

    def init(self):
        self.request_sent_count = 0
        self.response_queue = deque()
        self.response_received_count = 0
        self.response_fed_count = 0

    async def close(self, reason: Optional[Exception] = None):
        if self.is_closed:
            return
        if isinstance(reason, BaseEx):
            await self.conn.send_message(
                Meta(
                    transmission_id=self.transmission_id,
                    packet_type=Meta.REQUEST,
                    packet_flags=self.method.flags | Meta.PacketFlag.CANCEL,
                ),
                ErrorMessage(
                    code=reason.code,
                    message=reason.message,
                    data=dumps(reason.data) if reason.data else '',
                ),
            )
            self.sent_end_message = True
        if self.method.client_streaming and not self.sent_end_message:
            await self.conn.send_message(
                Meta(
                    transmission_id=self.transmission_id,
                    packet_type=Meta.REQUEST,
                    packet_flags=self.method.flags | Meta.PacketFlag.END,
                ),
                Void(),
            )
        await super().close(reason)

    def feed_message(self, meta, payload):
        '''Received response from transport layer '''
        assert meta.packet_type == Meta.RESPONSE, \
            f'invalid {meta.packet_type=}'
        if self.response_fed_count > 0 and not self.method.server_streaming:
            raise RPCError.MultipleResponseForUnaryMethod(
                data={
                    'service_method': self.method.name,
                    'transmission_id': self.transmission_id,
                }
            )

        if meta.is_failed or meta.is_cancelled:
            assert payload, 'should return error message'
            err = ErrorMessage.FromString(payload)
            ex = ErrorManager.assemble(
                err.code, err.message, err.data and loads(err.data) or {}
            )
            self.response_queue.append(ex)
        elif payload:
            self.response_queue.append(
                self.method.response_class.FromString(payload)
            )
        if meta.packet_flags & Meta.PacketFlag.END:
            self.response_queue.append(None)
        if self.waiter and not self.waiter.done():
            self.waiter.set_result(True)

    async def send_message(self, request=None, *, end: bool = False, **kwargs):
        '''Send request to transport layer'''
        if self.request_sent_count > 0 and not self.method.client_streaming:
            raise RPCError.RPCRequestSent(
                data={
                    'service_method': self.method.name,
                    'transmission_id': self.transmission_id,
                }
            )

        flags = self.method.flags
        if end or not self.method.client_streaming:
            flags |= Meta.PacketFlag.END
            self.sent_end_message = True
        await self.conn.send_message(
            Meta(
                transmission_id=self.transmission_id,
                service_method=self.method.name,
                packet_type=Meta.REQUEST,
                packet_flags=flags,
            ),
            request or self.method.request_class(**kwargs)
        )

    async def recv_message(self):
        '''Wait for response from logic layer

        In any cases, this should be called by the same one logic.
        '''
        if not self.method.require_response:
            return None

        if (self.response_received_count > 0
                and not self.method.server_streaming):
            raise RPCError.RPCResponseReceived(
                data={
                    'service_method': self.method.name,
                    'transmission_id': self.transmission_id,
                }
            )
        if not self.response_queue:
            assert self.waiter is None, \
                'should not called parallelly at the same time'
            self.waiter = Future()
            try:
                await self.waiter
            finally:
                self.waiter = None
        self.response_received_count += 1
        resp = self.response_queue.popleft()
        if isinstance(resp, Exception):
            raise resp
        return resp


C = TypeVar('Context', bound=Context)
