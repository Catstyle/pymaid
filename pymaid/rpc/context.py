from collections import deque
from functools import partial
from typing import Optional, TypeVar, Union

from pymaid.core import get_running_loop
from pymaid.core import Future, TimeoutError
from pymaid.error import BaseEx
from pymaid.utils.logger import logger_wrapper

from .error import RPCError
from .method import Method, MethodStub
from .types import ConnectionType

__all__ = ('C', 'Context', 'InboundContext', 'OutboundContext')


@logger_wrapper(name='pymaid.Context')
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
        self.conn_id = conn.id
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

    def feed_message(self, message):
        '''Received request from transport layer'''
        raise NotImplementedError('feed_message')

    async def run(self):
        await self.method(self)

    async def shutdown(self):
        pass

    async def close(self, reason: Union[str, Exception] = 'successful'):
        if self.is_closed:
            return
        self.logger.debug(f'{self!r} closed with [reason|{reason}]')
        self.is_closed = True
        if hasattr(self, '_manager'):
            self._manager.release_context(self.transmission_id)
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
        self.logger.debug(f'{self!r} cancelled with [reason|{reason}]')
        self.is_cancelled = True
        await self.close(reason)

    async def send_message(
        self, data=None, *, end: bool = False, **kwargs
    ):
        '''Send message to transport layer'''
        raise NotImplementedError('send_message')

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
        m = await self.recv_message()
        if m:
            return m
        raise StopAsyncIteration()

    def __repr__(self):
        return (
            f'<{self.__class__.__name__} conn={self.conn_id} '
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
            await self.handle_error(reason)
        if self.method.server_streaming and not self.sent_end_message:
            await self.shutdown()
        await super().close(reason)

    async def recv_message(self):
        '''Wait for request from logic layer

        In any cases, this should be called by the same one logic.
        '''
        if (self.request_received_count > 0
                and not self.method.client_streaming):
            raise RPCError.RPCRequestReceived(
                data={
                    'service_method': self.method.full_name,
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
            await self.handle_error(reason)
        if self.method.client_streaming and not self.sent_end_message:
            await self.shutdown()
        await super().close(reason)

    async def recv_message(self):
        '''Wait for response from logic layer

        In any cases, this should be called by the same one logic.
        '''
        if self.method.options.get('void_response'):
            return None

        if (self.response_received_count > 0
                and not self.method.server_streaming):
            raise RPCError.RPCResponseReceived(
                data={
                    'service_method': self.method.full_name,
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


class ContextManager:

    MAX_TRANSMISSION_ID = 2 ** 32 - 1
    INBOUND_CONTEXT_CLASS = InboundContext
    OUTBOUND_CONTEXT_CLASS = OutboundContext

    def __init__(self, initiative: bool):
        # for initiative side, the id will be EVEN
        # for passive side, the id will be ODD
        self.initiative = initiative
        self.outbound_transmission_id = 1 if initiative else 2
        self.contexts = {}

    def next_transmission_id(self) -> int:
        '''Return the next available transmission id for the context created
        by this endpoint.

        :raises: :class:`NoAvailableTransmissionID
            <pymaid.rpc.error.RPCError.NoAvailableTransmissionID>`
        :returns: the next id can be initiate a Context
        :rtype: ``int``
        '''
        transmission_id = self.outbound_transmission_id
        if transmission_id > self.MAX_TRANSMISSION_ID:
            raise RPCError.NoAvailableTransmissionID(
                data={'id': transmission_id, 'max': self.MAX_TRANSMISSION_ID}
            )
        self.outbound_transmission_id += 2
        return transmission_id

    def new_inbound_context(
        self,
        transmission_id: int,
        *,
        method: Method,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ) -> 'C':
        # it is hard to insist the inbound_transmission_id order
        # e.g.
        # client make 3 async calls: 1, 3, 5
        # all 3 run parallelly, then the order is unspecified

        # if transmission_id < self.inbound_transmission_id:
        #     raise RPCError.InvalidTransmissionID(
        #         data={
        #             'tid': transmission_id,
        #             'reason': 'reused transmission id',
        #         }
        #     )

        transmission_id = transmission_id
        assert transmission_id not in self.contexts, 'reused transmission id'
        if not self.initiative and transmission_id % 2 != 1:
            raise RPCError.InvalidTransmissionID(
                data={
                    'tid': transmission_id,
                    'reason': 'invalid inbound transmission id value',
                }
            )
        # self.inbound_transmission_id = transmission_id

        # warning: cyclic referrence
        context = self.INBOUND_CONTEXT_CLASS(
            conn=conn,
            transmission_id=transmission_id,
            method=method,
            timeout=timeout,
        )
        context._manager = self
        self.contexts[transmission_id] = context
        return context

    def new_outbound_context(
        self,
        *,
        method: MethodStub,
        conn: ConnectionType,
        timeout: Optional[float] = None,
    ) -> 'C':
        transmission_id = self.next_transmission_id()
        # warning: cyclic referrence
        context = self.OUTBOUND_CONTEXT_CLASS(
            conn=conn,
            transmission_id=transmission_id,
            method=method,
            timeout=timeout,
        )
        context._manager = self
        self.contexts[transmission_id] = context
        return context

    def get_context(self, transmission_id: int) -> 'C':
        return self.contexts.get(transmission_id)

    def release_context(self, transmission_id: int):
        if transmission_id not in self.contexts:
            # already released ?
            return
        context = self.contexts.pop(transmission_id)
        del context._manager


C = TypeVar('Context', bound=Context)
