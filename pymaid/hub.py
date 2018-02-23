from functools import wraps

from gevent import get_hub
from gevent.pool import Pool

greenlet_pool = Pool()
hub = get_hub()
io = hub.loop.io
timer = hub.loop.timer
signal = hub.loop.signal


def greenlet_worker(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return greenlet_pool.apply_async(func, args=args, kwds=kwargs)
    return wrapper
