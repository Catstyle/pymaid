import abc
from queue import deque
from typing import Optional, Union

from orjson import dumps

from pymaid.core import create_task, Event
from pymaid.error import BaseEx
from pymaid.ext.pools.worker import AioPool
from pymaid.rpc.pymaid_pb2 import Context as Meta, ErrorMessage
from pymaid.rpc.router import ServiceRepository
from pymaid.utils.logger import logger_wrapper

from .error import PBError


@logger_wrapper
class Handler(abc.ABC):
    '''Handle the *received* request/response.'''

    def __init__(
        self,
        service_repository: ServiceRepository,
        timeout: Optional[float] = None,
    ):
        self.service_repository = service_repository
        self.timeout = timeout

        self.pending_tasks = deque()
        self.new_task_received = Event()
        self.is_closing = False
        self.is_closed = False

        self.task = create_task(self.run())

    async def run(self):
        # callbacks = {
        #     Meta.PacketType.REQUEST: self.handle_request,
        #     Meta.PacketType.RESPONSE: self.handle_response,
        # }

        new_task_received = self.new_task_received
        pending_tasks = self.pending_tasks

        while 1:
            await new_task_received.wait()
            while len(pending_tasks):
                task = pending_tasks.popleft()
                if not task:
                    return
                meta, coro = task
                # if callback for packet_type not exists, just let it crash
                try:
                    await task
                except BaseEx as exc:
                    assert False, f'{exc} should be handled within logic'
                    # meta.is_failed = True
                    # packet = ErrorMessage(code=exc.code, message=exc.message)
                    # if exc.data:
                    #     packet.data = dumps(exc.data)
                    # await self.conn.send_message(meta, packet)
                except Exception as exc:
                    await self.close(exc, join=False)
                    return
            new_task_received.clear()

    async def join(self):
        if self.is_closed:
            return
        self.pending_tasks.append(None)
        self.new_task_received.set()
        await self.task

    async def close(
        self, exc: Optional[Union[str, Exception]] = None, join: bool = True,
    ):
        if self.is_closed:
            return
        # maybe called from run loop
        if join:
            await self.join()
        self.is_closed = True
        self.pending_tasks.clear()
        await self.conn.close(exc)
        self.conn = None

    def feed_message(self, pending_tasks):
        # self.logger.debug(f'{self} feed {len(pending_tasks)=}')
        Request = Meta.PacketType.REQUEST
        Response = Meta.PacketType.RESPONSE
        get_service_method = self.service_repository.get_service_method
        for message in pending_tasks:
            # check exist context here for a shortcut
            # because just feed message into context won't block,
            # and it makes serial streaming posible
            meta, payload = message
            if context := self.conn.get_context(meta.transmission_id):
                context.feed_message(meta, payload)
                continue

            if meta.packet_type not in {Request, Response}:
                task = self.handle_error(
                    meta,
                    PBError.InvalidPacketType(
                        data={'packet_type': meta.packet_type}
                    )
                )
            elif meta.packet_type == Request:
                name = meta.service_method
                if (rpc := get_service_method(name)) is None:
                    task = self.handle_error(
                        meta, PBError.RPCNotFound(data={'name': name})
                    )
                else:
                    context = self.conn.new_inbound_context(
                        meta.transmission_id, method=rpc, timeout=self.timeout
                    )
                    context.feed_message(meta, payload)
                    task = context.run()
            elif meta.packet_type == Response:
                # invalid transmission_id, do nothing
                self.logger.warning(
                    f'{self.conn} received invalid response, '
                    f'{meta.transmission_id=}'
                )
                continue
            self.pending_tasks.append(task)
            self.new_task_received.set()

    # @abc.abstractmethod
    # async def handle_request(self, meta, payload):
    #     raise NotImplementedError('handle_request')

    # def handle_response(self, meta, payload):
    #     self.logger.debug(f'{self} handle_response {meta!r}')
    #     if (context := self.conn.get_context(meta.transmission_id)) is None:
    #         # invalid transmission_id, do nothing
    #         self.logger.warning(
    #             f'{self.conn} received invalid response, '
    #             f'{meta.transmission_id=}'
    #         )
    #         return
    #     context.feed_message(meta, payload)

    async def handle_error(self, meta, error):
        meta.is_failed = True
        meta.packet_type = Meta.PacketType.RESPONSE
        packet = ErrorMessage(code=error.code, message=error.message)
        if error.data:
            packet.data = dumps(error.data)
        await self.conn.send_message(meta, packet)

    def __repr__(self):
        return (
            f'<{self.__class__.__name__}@{id(self)} '
            f'pending={len(self.pending_tasks)}>'
        )


@logger_wrapper
class SerialHandler(Handler):
    '''Handle the *received* request/response *one by one*.

    Even for streaming method, it will still in serial order.
    '''

    async def run(self):
        # callbacks = {
        #     Meta.PacketType.REQUEST: self.handle_request,
        #     Meta.PacketType.RESPONSE: self.handle_response,
        # }

        new_task_received = self.new_task_received
        pending_tasks = self.pending_tasks

        while 1:
            await new_task_received.wait()
            while len(pending_tasks):
                task = pending_tasks.popleft()
                if not task:
                    return
                # if callback for packet_type not exists, just let it crash
                try:
                    await task
                except BaseEx as exc:
                    assert False, f'{exc} should be handled within logic'
                    # meta.is_failed = True
                    # packet = ErrorMessage(code=exc.code, message=exc.message)
                    # if exc.data:
                    #     packet.data = dumps(exc.data)
                    # await self.conn.send_message(meta, packet)
                except Exception as exc:
                    await self.close(exc, join=False)
                    return
            new_task_received.clear()

    # async def handle_request(self, meta, payload):
    #     self.logger.debug(f'{self} handle_request {meta!r}')
    #     if context := self.conn.get_context(meta.transmission_id):
    #         context.feed_message(meta, payload)
    #         return

    #     name = meta.service_method
    #     if (rpc := self.service_repository.get_service_method(name)) is None:
    #         raise PBError.RPCNotFound(data={'name': name})
    #     context = self.conn.new_inbound_context(
    #         meta.transmission_id, method=rpc, timeout=self.timeout
    #     )
    #     context.feed_message(meta, payload)
    #     await rpc(context)


@logger_wrapper
class ParallelHandler(Handler):
    '''Handle the *received* request/response parallelly.

    It holds a worker pool to do the actual work, with a limited concurrency.
    '''

    def __init__(
        self,
        service_repository: ServiceRepository,
        timeout: Optional[float] = None,
        concurrency: int = 5,
    ):
        super().__init__(service_repository, timeout)
        self.worker = AioPool(concurrency)

    async def join(self):
        if self.is_closed:
            return
        self.pending_tasks.append(None)
        self.new_task_received.set()
        await self.task
        await self.worker.shutdown(wait=True)

    async def run(self):
        # callbacks = {
        #     Meta.PacketType.REQUEST: self.handle_request,
        #     Meta.PacketType.RESPONSE: self.handle_response,
        # }

        new_task_received = self.new_task_received
        pending_tasks = self.pending_tasks
        # run_task = self.worker.submit
        run_task = self.worker.spawn

        while 1:
            await new_task_received.wait()
            while len(pending_tasks):
                task = pending_tasks.popleft()
                if not task:
                    return
                # if callback for packet_type not exists, just let it crash
                try:
                    await run_task(task)
                except BaseEx as exc:
                    assert False, f'{exc} should be handled within logic'
                    # meta.is_failed = True
                    # packet = ErrorMessage(code=exc.code, message=exc.message)
                    # if exc.data:
                    #     packet.data = dumps(exc.data)
                    # await self.conn.send_message(meta, packet)
                except Exception as exc:
                    await self.close(exc, join=False)
                    return
            new_task_received.clear()

    # async def handle_request(self, meta, payload):
    #     # self.logger.debug(f'{self} handle_request {meta}')
    #     if context := self.conn.get_context(meta.transmission_id):
    #         context.feed_message(meta, payload)
    #         return

    #     name = meta.service_method
    #     if (rpc := self.service_repository.get_service_method(name)) is None:
    #         raise PBError.RPCNotFound(data={'name': name})
    #     context = self.conn.new_inbound_context(
    #         meta.transmission_id, method=rpc, timeout=self.timeout
    #     )
    #     context.feed_message(meta, payload)
    #     await self.worker.spawn(rpc(context))
