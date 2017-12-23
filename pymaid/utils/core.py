import sys
import inspect
import traceback
from functools import wraps

from gevent import get_hub
from gevent import signal
from gevent.pool import Pool

greenlet_pool = Pool()
hub = get_hub()
io = hub.loop.io
timer = hub.loop.timer


def implall(service):
    service_name = service.DESCRIPTOR.name
    for base in service.__bases__:
        for method in base.DESCRIPTOR.methods:
            method_name = method.name
            base_method = getattr(base, method_name)
            impl_method = getattr(service, method_name, base_method)
            if base_method == impl_method:
                raise RuntimeError(
                    '%s.%s is not implemented' % (service_name, method_name)
                )
    return service


def greenlet_worker(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return greenlet_pool.apply_async(func, args=args, kwds=kwargs)
    return wrapper


def enable_autoreload(signum):
    from .autoreload import ModuleReloader
    reloader = ModuleReloader()
    reloader.enabled = True

    def autoreload(sig, frame):
        reloader.check()
    signal.signal(signum, autoreload)


def enable_debug_output(signum):

    def debug_output(sig, frame):
        sys.stderr.write('############## pymaid debug_output ##############\n')
        for tid, frame in sys._current_frames().iteritems():
            sys.stderr.write('\n')
            sys.stderr.write('thread: %s\n' % tid)
            sys.stderr.write(
                ''.join(traceback.format_list(traceback.extract_stack(frame)))
            )
            sys.stderr.write('%s' % str(inspect.getargvalues(frame)))
    signal.signal(signum, debug_output)
