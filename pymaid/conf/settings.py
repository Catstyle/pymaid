from __future__ import absolute_import

import warnings
from importlib import import_module
import ujson as json

from gevent.event import AsyncResult

from pymaid.utils.core import greenlet_worker
from pymaid.utils.logger import pymaid_logger_wrapper

from . import defaults


@pymaid_logger_wrapper
class Settings(object):

    def __init__(self):
        self.load_from_object(defaults)

    def _configure_logging(self):
        """Setup logging from LOGGING_CONFIG and LOGGING settings."""
        import logging
        import logging.config
        try:
            # Route warnings through python logging
            logging.captureWarnings(True)
            # Allow DeprecationWarnings through the warnings filters
            warnings.simplefilter("default", DeprecationWarning)
        except AttributeError:
            # No captureWarnings on Python 2.6
            # DeprecationWarnings are on anyway
            pass

        if hasattr(self, 'PYMAID_LOGGING'):
            logging.config.dictConfig(self.PYMAID_LOGGING)
        if hasattr(self, 'LOGGING'):
            logging.config.dictConfig(self.LOGGING)

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
        for setting in dir(obj):
            if setting == setting.upper():
                setattr(self, setting, getattr(obj, setting))
        self._configure_logging()
        self.logger.debug(
            '[pymaid][settings] configured [%s]',
            {attr: value for attr, value in self.__dict__.items()
             if attr == attr.upper()}
        )

    @greenlet_worker
    def load_from_backend(self, backend):
        for data in backend:
            self.logger.debug(
                '[pymaid][settings][backend|%s] receive [data|%r]',
                backend, data
            )
            for setting in data:
                if setting == setting.upper():
                    setattr(self, setting, data[setting])
            self._configure_logging()
            self.logger.debug(
                '[pymaid][settings] configured [%s]',
                {attr: value for attr, value in self.__dict__.items()
                 if attr == attr.upper()}
            )


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
                yield json.loads(resp['data'])


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
            yield json.loads(result.get())
            result = AsyncResult()


settings = Settings()
