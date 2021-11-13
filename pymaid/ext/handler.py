import abc

from queue import deque
from typing import Callable, Coroutine, List, Optional, Union

from pymaid.core import create_task, current_task, Event, Task
from pymaid.core import get_running_loop, iscoroutine, iscoroutinefunction
from pymaid.error import BaseEx
from pymaid.ext.pools.worker import AioPool
from pymaid.utils.logger import logger_wrapper


class Handler(abc.ABC):
    '''Handle the *received* tasks.'''

    def __init__(
        self,
        *,
        on_close: Optional[List[Callable[['Handler'], None]]] = None,
        error_handler: Optional[Callable[[Task], Coroutine]] = None,
        close_on_exception: bool = False,
    ):
        self.task = None
        self.on_close = on_close or []
        self.close_on_exception = close_on_exception

        if error_handler:
            if not iscoroutinefunction(error_handler):
                raise ValueError('required error_handler as coroutinefunction')
            self.error_handler = error_handler
        else:
            self.error_handler = self.handle_error

        self.pending_tasks = deque()
        self.new_task_received = Event()
        self.closed_event = Event()
        self.is_closing = False
        self.is_closed = False

        self.task = create_task(self.run())

    @abc.abstractmethod
    async def run(self):
        raise NotImplementedError('run')

    def shutdown(self, reason: Union[None, str, Exception] = None):
        if self.is_closing:
            return
        self.logger.debug(f'{self!r} shutdown with reason={reason!r}')
        self.is_closing = True
        self.pending_tasks.append(None)
        self.new_task_received.set()

    async def join(self, reason: Optional[Union[str, Exception]] = None):
        if current_task() is self.task:
            raise RuntimeError('cannot join self')
        if not self.is_closing:
            raise RuntimeError('cannot join, call shutdown first')
        await self.closed_event.wait()

    def close(self, reason: Optional[Union[str, Exception]] = None):
        if self.is_closed:
            return
        self.logger.info(f'{self!r} close with reason={reason!r}')
        self.is_closed = True
        for task in self.pending_tasks:
            if iscoroutine(task):
                task.close()
        self.pending_tasks.clear()

        for cb in self.on_close:
            cb(self)
        self.closed_event.set()
        if not self.task.done():
            self.task.cancel()
        self.task = None

    def submit(self, task: Callable, *args, **kwargs):
        # self.logger.debug(f'{self!r} get task={task}')
        self.pending_tasks.append((task, args, kwargs))
        self.new_task_received.set()

    async def handle_error(self, error: Exception):
        '''Default error handler.

        Just write error logs.
        '''
        self.logger.error(f'{self!r} caught an unhandled error, {error!r}')

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_tpye, exc_value, exc_tb):
        self.shutdown('__aexit__')
        await self.join()

    def __repr__(self):
        return (
            f'<{self.__class__.__name__} '
            f'pending={len(self.pending_tasks)} '
            f'close_on_exception={self.close_on_exception}'
            f'>'
        )


@logger_wrapper(name='pymaid.SerialHandler')
class SerialHandler(Handler):
    '''Handle the *received* tasks *one by one*.

    This is usually used for stateful situation, like games, the previous task
    will mostly impact the later one.
    '''

    async def run(self):
        new_task_received = self.new_task_received
        pending_tasks = self.pending_tasks
        error_handler = self.error_handler

        running = True
        while running:
            await new_task_received.wait()
            # clear for reuse
            new_task_received.clear()
            while pending_tasks:
                task = pending_tasks.popleft()
                if not task:
                    running = False
                    break

                task, args, kwargs = task
                try:
                    if iscoroutine(task):
                        await task
                    elif iscoroutinefunction(task):
                        await task(*args, **kwargs)
                    else:
                        task(*args, **kwargs)
                except BaseEx as exc:
                    assert False, f'{exc} should be handled within logic'
                except Exception as exc:
                    await error_handler(exc)
                    if self.close_on_exception:
                        self.close(exc)
                        return
        self.close()


@logger_wrapper(name='pymaid.ParallelHandler')
class ParallelHandler(Handler):
    '''Handle the *received* tasks parallelly.

    It holds a worker pool to do the actual work, with a limited concurrency.
    '''

    def __init__(
        self,
        *,
        on_close: Optional[List[Callable[['Handler'], None]]] = None,
        error_handler: Optional[Callable[[Task], Coroutine]] = None,
        close_on_exception: bool = False,
        concurrency: int = 5,
    ):
        super().__init__(
            on_close=on_close,
            error_handler=error_handler,
            close_on_exception=close_on_exception,
        )
        self.worker = AioPool(concurrency)
        self.got_exception = False

    async def _run_callback(self, callback: Callable, *args, **kwargs):
        return callback(*args, **kwargs)

    def _discard_result(self, task: Task):
        if task.cancelled():
            return
        try:
            task.result()
        except BaseEx as exc:
            assert False, f'{exc} should be handled within logic'
            del exc
        except Exception as exc:
            get_running_loop().create_task(self.error_handler(exc))
            if self.close_on_exception:
                self.got_exception = True
                get_running_loop().create_task(self.on_exception(exc))

    async def join(self, reason: Optional[Union[str, Exception]] = None):
        await self.worker.join()
        await super().join(reason)

    async def on_exception(self, exc: Exception):
        await self.worker.join()
        self.close(exc)

    async def run(self):
        new_task_received = self.new_task_received
        pending_tasks = self.pending_tasks
        error_handler = self.error_handler
        schedule_task = self.worker.spawn
        run_callback = self._run_callback

        running = True
        while running:
            await new_task_received.wait()
            # clear for reuse
            new_task_received.clear()
            while pending_tasks:
                task = pending_tasks.popleft()
                if not task:
                    running = False
                    break

                task, args, kwargs = task
                try:
                    if iscoroutine(task):
                        pass
                    elif iscoroutinefunction(task):
                        task = task(*args, **kwargs)
                    else:
                        task = run_callback(task, *args, **kwargs)
                    assert iscoroutine(task), task
                    t = await schedule_task(task, self._discard_result)
                    if self.close_on_exception and self.got_exception:
                        self.logger.warning(
                            'cancel task due to close_on_exception'
                        )
                        t.cancel()
                except Exception as exc:
                    await error_handler(exc)
                    if self.close_on_exception:
                        await self.worker.join()
                        self.close(exc)
                        return
        await self.worker.join()
        self.close()
