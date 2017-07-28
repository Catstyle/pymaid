from __future__ import absolute_import

from importlib import import_module
from ujson import loads

from gevent.event import AsyncResult

from pymaid.utils.core import greenlet_worker
from pymaid.utils.logger import configure_logging, pymaid_logger_wrapper

from . import defaults


@pymaid_logger_wrapper
class Settings(object):

    def __init__(self):
        self.watchers = []
        self.data = {}

    def add_watcher(self, watcher):
        if watcher in self.watchers:
            return
        self.watchers.append(watcher)

    def load_from_module(self, module_name):
        """Load the settings module pointed to by the module_name.

        This is used the first time we need any settings at all,
        if the user has not previously configured the settings manually.

        The user can manually configure settings prior to using them.
        """
        try:
            mod = import_module(module_name)
        except ImportError as e:
            raise ImportError(
                "Could not import settings '%s' (Is it on sys.path?): %s" % (
                    module_name, e
                )
            )
        self.load_from_object(mod)

    def load_from_object(self, obj):
        data = {}
        if isinstance(obj, dict):
            data.update({
                key: value for key, value in obj.items() if key == key.upper()
            })
        else:
            data.update({
                key: getattr(obj, key)
                for key in dir(obj) if key == key.upper()
            })
        self.data.update(data)
        for key, value in data.items():
            setattr(self, key, value)
        self.logger.debug(
            '[pymaid][settings] configured [%s]',
            [(key, value) for key, value in sorted(self.data.items())
             if 'SECRET' not in key]
        )
        for watcher in self.watchers:
            watcher(self)

    @greenlet_worker
    def load_from_backend(self, backend):
        for data in backend:
            self.logger.debug(
                '[pymaid][settings][backend|%s] receive [data|%r]',
                backend, data
            )
            self.load_from_object(data)


class SettingsBackend(object):

    def __iter__(self):
        raise NotImplementedError

    def __str__(self):
        return self.__class__.__name__
    __repr__ = __str__


@pymaid_logger_wrapper
class RedisBackend(SettingsBackend):

    def __init__(self, rdb, channel):
        subscriber = rdb.pubsub()
        subscriber.subscribe(channel)
        self.generator = subscriber.listen()

    def __iter__(self):
        # first resp is subscribe info
        self.generator.next()
        for resp in self.generator:
            if resp['data']:
                yield loads(resp['data'])


@pymaid_logger_wrapper
class ZooKeeperBackend(SettingsBackend):

    def __init__(self, zk, path):
        self.zk = zk
        self.path = path

    def __iter__(self):
        result = AsyncResult()

        @self.zk.DataWatch(self.path)
        def watcher(data, stat):
            if data:
                result.set(data)

        while 1:
            yield loads(result.get())
            result = AsyncResult()


settings = Settings()
settings.add_watcher(configure_logging)
settings.load_from_object(defaults)
