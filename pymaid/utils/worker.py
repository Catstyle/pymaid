import sys
from functools import wraps

import gevent
from gevent.queue import JoinableQueue
from gevent.event import AsyncResult

from .core import hub


class Worker(object):

    def __init__(self):
        self.queue = JoinableQueue()
        self._worker = gevent.spawn(self._run)

    @property
    def pending_tasks(self):
        return self.queue.qsize()

    def _run(self):
        get_task, task_done = self.queue.get, self.queue.task_done
        while 1:
            task = get_task()
            if not task:
                break
            func, args, kwargs, result = task
            try:
                resp = func(*args, **kwargs)
                result.set(resp)
            except Exception as ex:
                hub.handle_error(task, *sys.exc_info())
                result.set_exception(ex)
            finally:
                task_done()

    def _apply(self, func, *args, **kwargs):
        result = AsyncResult()
        self.queue.put((func, args, kwargs, result))
        return result

    def apply(self, func, *args, **kwargs):
        return self._apply(func, *args, **kwargs)

    def apply_delay(self, func, delay, *args, **kwargs):
        self._apply(gevent.sleep, delay)
        return self._apply(func, *args, **kwargs)

    def join(self):
        self.queue.put(None)
        self.queue.join()


def queue_worker(cls):
    original_init = cls.__init__

    def init(self, *args, **kwargs):
        self._worker = Worker()
        original_init(self, *args, **kwargs)

    cls.__init__ = init
    return cls


def apply_worker(func):
    @wraps(func)
    def _(self, *args, **kwargs):
        return self._worker.apply(func, self, *args, **kwargs)
    return _


def apply_delay_worker(delay):
    def wrapper(func):
        @wraps(func)
        def _(self, *args, **kwargs):
            return self._worker.apply_delay(func, delay, self, *args, **kwargs)
        return _
    return wrapper
