from functools import wraps

import gevent
from gevent import get_hub
from gevent.event import AsyncResult, Event
from gevent.pool import Pool
from gevent.queue import JoinableQueue

__all__ = [
    'hub', 'io', 'timer', 'signal', 'greenlet_pool', 'greenlet_worker',
    'AsyncResult', 'Event', 'Pool', 'JoinableQueue',
]

greenlet_pool = Pool()
hub = get_hub()
io = hub.loop.io
timer = hub.loop.timer
signal = hub.loop.signal

serve_forever = gevent.wait
sleep = gevent.sleep
spawn = gevent.spawn


def greenlet_worker(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return greenlet_pool.apply_async(func, args=args, kwds=kwargs)
    return wrapper


class AsyncResult(AsyncResult):
    # need to set attribute to AsyncResult
    pass
