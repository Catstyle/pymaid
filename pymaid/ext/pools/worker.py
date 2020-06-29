from typing import Callable, Coroutine, Optional

from pymaid.core import Event, Semaphore, Task
from pymaid.core import current_task, iscoroutine


class AioPool:

    def __init__(self, size: Optional[int] = None, *, task_class=None):
        if size is None:
            size = 2048
        if size <= 0:
            raise ValueError(f'size must be positive: {size}')

        task_class = task_class or Task
        if not issubclass(task_class, Task):
            raise TypeError(
                f'task_class expected to be subclass of Task, got: {task_class}'
            )
        self.task_class = task_class

        self.size = size
        self.tasks = set()
        self.semaphore = Semaphore(size)
        self.empty_event = Event()

        self.has_shutdown = False
        self.executed_count = 0

    @property
    def is_empty(self):
        return len(self.tasks) == 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_tpye, exc_value, exc_tb):
        await self.join()

    async def _run(self, coro, callback=None):
        try:
            result = await coro
            if callback is not None:
                callback(result)
            else:
                return result
        finally:
            self.executed_count += 1
            self.task_done(current_task())

    async def _spawn(self, coro, callback=None):
        await self.semaphore.acquire()
        try:
            return await self._run(coro, callback)
        finally:
            self.semaphore.release()

    def task_done(self, task):
        assert task in self.tasks, 'task not belong to this pool'
        self.tasks.remove(task)
        if self.is_empty:
            self.notify_empty()

    async def spawn(self, coro: Coroutine, callback: Optional[Callable] = None) -> Task:
        '''submit coroutine to the pool, waiting for pool space.

        coroutine is executed in pool when pool space is available.
        '''
        if self.has_shutdown:
            raise RuntimeError('cannot call spawn after shutdown')

        if not iscoroutine(coro):
            raise TypeError(f'coro expected to be coroutine, got: {coro}')

        if not callable(callback):
            raise TypeError(f'callback expected to be callable, got: {callback}')

        await self.semaphore.acquire()
        task = self.task_class(self._run(coro, callback=callback))
        task.add_done_callback(lambda t: self.semaphore.release())
        self.tasks.add(task)
        return task

    def submit(self, coro: Coroutine, callback: Optional[Callable] = None) -> Task:
        '''submit coroutine to the pool, without waiting for pool space.

        coroutine is executed in pool when pool space is available.
        '''
        if self.has_shutdown:
            raise RuntimeError('cannot call submit after shutdown')

        if not iscoroutine(coro):
            raise TypeError(f'coro expected to be coroutine, got: {coro}')

        if not callable(callback):
            raise TypeError(f'callback expected to be callable, got: {callback}')

        task = self.task_class(self._spawn(coro, callback=callback))
        self.tasks.add(task)
        return task

    async def shutdown(self, wait=True):
        self.shutdown = True
        if wait:
            await self.join()

    async def join(self):
        if current_task() in self.tasks:
            raise RuntimeError(
                'cannot call join within task spawned by the pool, '
                'it will cause deadlock'
            )

        if not self.is_empty:
            await self.empty_event.wait()

    def notify_empty(self):
        ''' wake up join waiters, reset empty_event for reusability.'''
        self.empty_event.set()
        self.empty_event.clear()
