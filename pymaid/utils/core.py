from gevent import get_hub
from gevent.pool import Pool

greenlet_pool = Pool()
hub = get_hub()
io = hub.loop.io
realtimer = hub.loop.timer


class Timer(object):

    def __init__(self, after, repeat, ref, priority, use_greenlet):
        self.realtimer = realtimer(after, repeat, ref, priority)
        if use_greenlet:
            self.start = self._start_async
            self.again = self._again_async

    def _start_async(self, callback, *args):
        self.realtimer.start(lambda *args: greenlet_pool.apply_async(callback, *args))

    def _again_async(self, callback, *args):
        self.realtimer.again(lambda *args: greenlet_pool.apply_async(callback, *args))

    def __getattr__(self, name):
        return getattr(self.realtimer, name)


def timer(after=0.0, repeat=0.0, ref=True, priority=None, use_greenlet=False):
    # run callback on a greentlet if greenlet=True
    return Timer(after, repeat, ref, priority, use_greenlet)


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
