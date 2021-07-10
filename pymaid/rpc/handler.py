import abc
from queue import deque
from typing import Optional, Union

from pymaid.core import create_task, Event
from pymaid.error import BaseEx
from pymaid.ext.pools.worker import AioPool
from pymaid.utils.logger import logger_wrapper

from .context import C, InboundContext, OutboundContext
from .error import RPCError
from .method import Method, MethodStub
from .router import Router


class Handler(abc.ABC):
    '''Handle the *received* request/response.'''

    MAX_TRANSMISSION_ID = 2 ** 32 - 1
    INBOUND_CONTEXT_CLASS = InboundContext
    OUTBOUND_CONTEXT_CLASS = OutboundContext

    def __init__(
        self,
        router: Router,
        timeout: Optional[float] = None,
    ):
        self.conn = None
        self.task = None
        self.router = router
        self.timeout = timeout

        # self.inbound_transmission_id = 0
        self.outbound_transmission_id = 0
        self.contexts = {}

        self.pending_tasks = deque()
        self.new_task_received = Event()
        self.closed_event = Event()
        self.is_closing = False
        self.is_closed = False

    def start(self, conn):
        # NOTE: cyclic
        self.conn = conn

        # for initiative side, the id will be EVEN
        # for passive side, the id will be ODD
        if conn.initiative:
            self.outbound_transmission_id = 1
        else:
            self.outbound_transmission_id = 2
        # cyclic
        self.task = create_task(self.run())

    def get_context(self, transmission_id: int) -> 'C':
        return self.contexts.get(transmission_id)

    def release_context(self, transmission_id: int):
        if transmission_id not in self.contexts:
            # already released ?
            return
        context = self.contexts.pop(transmission_id)
        del context._manager

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
        if not self.conn.initiative and transmission_id % 2 != 1:
            raise RPCError.InvalidTransmissionID(
                data={
                    'tid': transmission_id,
                    'reason': 'invalid inbound transmission id value',
                }
            )
        # self.inbound_transmission_id = transmission_id

        # warning: cyclic referrence
        context = self.INBOUND_CONTEXT_CLASS(
            conn=self.conn,
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
        timeout: Optional[float] = None,
    ) -> 'C':
        transmission_id = self.next_transmission_id()
        # warning: cyclic referrence
        context = self.OUTBOUND_CONTEXT_CLASS(
            conn=self.conn,
            transmission_id=transmission_id,
            method=method,
            timeout=timeout,
        )
        context._manager = self
        self.contexts[transmission_id] = context
        return context

    @abc.abstractmethod
    async def run(self):
        raise NotImplementedError('run')

    def shutdown(self, reason: Union[None, str, Exception] = None):
        if self.is_closing:
            return
        self.is_closing = True
        self.pending_tasks.append(None)
        self.new_task_received.set()

    async def join(self, reason: Optional[Union[str, Exception]] = None):
        await self.closed_event.wait()

    def close(self, reason: Optional[Union[str, Exception]] = None):
        if self.is_closed:
            return
        self.is_closed = True
        self.pending_tasks.clear()
        self.closed_event.set()
        self.conn.close(reason)
        if not self.task.done():
            self.task.cancel()
        del self.conn
        del self.task

    @abc.abstractmethod
    def feed_messages(self, messages):
        # self.logger.debug(f'{self!r} feed size={len(messages)}')
        raise NotImplementedError('feed_messages')

    async def handle_error(self, error):
        '''Default error handler.

        Just write error logs.
        '''
        self.logger.error(f'{self!r} caught an unhandled error, {error!r}')

    def __repr__(self):
        return (
            f'<{self.__class__.__name__} '
            f'pending={len(self.pending_tasks)}>'
        )


@logger_wrapper(name='pymaid.SerialHandler')
class SerialHandler(Handler):
    '''Handle the *received* requests *one by one*.

    Even for streaming method, it will still in serial order.

    This is usually used for stateful situation, like gaming, the previous
    request mostly will impact the later one.
    '''

    async def run(self):
        new_task_received = self.new_task_received
        pending_tasks = self.pending_tasks

        while 1:
            await new_task_received.wait()
            while pending_tasks:
                task = pending_tasks.popleft()
                if not task:
                    self.close()
                    return
                try:
                    await task
                except BaseEx as exc:
                    assert False, f'{exc} should be handled within logic'
                except Exception as exc:
                    self.close(exc)
                    return
            new_task_received.clear()


@logger_wrapper(name='pymaid.ParallelHandler')
class ParallelHandler(Handler):
    '''Handle the *received* requests parallelly.

    It holds a worker pool to do the actual work, with a limited concurrency.
    '''

    def __init__(
        self,
        router: Router,
        timeout: Optional[float] = None,
        concurrency: int = 5,
    ):
        super().__init__(router, timeout)
        self.worker = AioPool(concurrency)

    async def join(self, reason: Optional[Union[str, Exception]] = None):
        await self.worker.shutdown(wait=True)
        await super().join(reason)

    async def run(self):
        new_task_received = self.new_task_received
        pending_tasks = self.pending_tasks
        # run_task = self.worker.submit
        run_task = self.worker.spawn

        while 1:
            await new_task_received.wait()
            while pending_tasks:
                task = pending_tasks.popleft()
                if not task:
                    self.close()
                    return
                try:
                    await run_task(task)
                except BaseEx as exc:
                    assert False, f'{exc} should be handled within logic'
                except Exception as exc:
                    self.close(exc)
                    return
            new_task_received.clear()
