from typing import Callable, Coroutine, Optional, TypeVar

from pymaid.core import Event, Semaphore, Task
from pymaid.core import current_task, iscoroutine


class AioPool:

    def __init__(self, size: int = 1024, *, task_class: TypeVar(Task) = Task):
        if size <= 0:
            raise ValueError(f'size must be positive: {size}')

        if not issubclass(task_class, Task):
            raise TypeError(
                f'task_class expected to be subclass of Task, '
                f'got: {task_class}'
            )
        self.task_class = task_class

        self.size = size
        self.semaphore = Semaphore(size)
        self.tasks = set()
        self.waiter_count = 0
        self.empty_event = Event()

        self.has_shutdown = False
        self.executed_count = 0

    @property
    def is_empty(self):
        return len(self.tasks) == 0 and not self.waiter_count

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_tpye, exc_value, exc_tb):
        await self.join()

    async def _spawn(self, coro):
        await self.semaphore.acquire()
        try:
            return await coro
        finally:
            self.task_done(current_task())

    def task_done(self, task):
        assert task in self.tasks, 'task not belong to this pool'
        self.semaphore.release()
        self.tasks.remove(task)
        self.executed_count += 1
        if self.is_empty:
            self.notify_empty()

    async def spawn(
        self, coro: Coroutine, callback: Optional[Callable] = None
    ) -> Task:
        '''Submit coroutine to the pool, waiting for pool space.

        coroutine is executed in pool when pool space is available.
        '''
        if self.has_shutdown:
            raise RuntimeError('cannot call spawn after shutdown')

        if not iscoroutine(coro):
            raise TypeError(f'coro expected to be coroutine, got: {coro}')

        if callback is not None and not callable(callback):
            raise TypeError(
                f'callback expected to be callable, got: {callback}'
            )

        self.waiter_count += 1
        await self.semaphore.acquire()
        self.waiter_count -= 1
        task = self.task_class(coro)
        task.add_done_callback(self.task_done)
        if callback:
            task.add_done_callback(callback)
        self.tasks.add(task)
        return task

    def submit(
        self, coro: Coroutine, callback: Optional[Callable] = None
    ) -> Task:
        '''Submit coroutine to the pool, without waiting for pool space.

        coroutine is executed in pool when pool space is available.
        '''
        if self.has_shutdown:
            raise RuntimeError('cannot call submit after shutdown')

        if not iscoroutine(coro):
            raise TypeError(f'coro expected to be coroutine, got: {coro}')

        if callback is not None and not callable(callback):
            raise TypeError(
                f'callback expected to be callable, got: {callback}'
            )

        task = self.task_class(self._spawn(coro, callback=callback))
        if callback:
            task.add_done_callback(callback)
        self.tasks.add(task)
        return task

    def shutdown(self):
        self.has_shutdown = True

    async def join(self):
        if current_task() in self.tasks:
            raise RuntimeError(
                'cannot call join within task spawned by the pool, '
                'it will cause deadlock'
            )

        if not self.is_empty:
            await self.empty_event.wait()

    def notify_empty(self):
        '''Wake up join waiters, reset empty_event for reusability.'''
        self.empty_event.set()
        self.empty_event.clear()
