from __future__ import absolute_import

from collections import defaultdict
from importlib import import_module
import os
import re

from pymaid.utils.logger import configure_logging, pymaid_logger_wrapper

from . import defaults


@pymaid_logger_wrapper
class Settings(object):

    def __init__(self, name):
        self.name = name
        self.namespaces = {}
        self.watchers = defaultdict(list)

    def filter(self, key, value):
        return key == key.upper()

    def get(self, key, default=None, ns='common'):
        """Return specified config value in local namespaces cache.

        This method will not block and return default value if key not exists.
        User should initiate settings manually by calling `load_from_*` apis.
        """
        try:
            return self.namespaces[ns][key]
        except KeyError:
            return default

    def add_watcher(self, watcher, ns='common'):
        if watcher in self.watchers[ns]:
            return
        self.watchers[ns].append(watcher)

    def load_from_object(self, obj, ns='common', mutable=True):
        if isinstance(obj, dict):
            ns = obj.get('__NAMESPACE__', ns)
        else:
            ns = getattr(obj, '__NAMESPACE__', ns)

        if (ns in self.namespaces and
                not self.namespaces[ns].get('__MUTABLE__', mutable)):
            self.logger.warn('[pymaid][settings][ns|%s] not mutable', ns)
            return False

        data = {}
        filter = self.filter
        if isinstance(obj, dict):
            data.update({
                key: value for key, value in obj.items() if filter(key, value)
            })
        else:
            data.update({
                key: getattr(obj, key)
                for key in dir(obj) if filter(key, getattr(obj, key))
            })
        self.namespaces.setdefault(ns, {}).update(data)
        self.namespaces[ns].setdefault(
            '__MUTABLE__', data.get('__MUTABLE__', mutable)
        )

        for watcher in self.watchers[ns]:
            watcher(self, ns)
        return True

    def load_from_module(self, module_name, ns='common', mutable=True):
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
        self.load_from_object(mod, getattr(mod, '__NAMESPACE__', ns), mutable)

    def load_from_root_path(self, path, ns='common', mutable=True):
        for root, dirs, files in os.walk(path):
            if '__init__.py' not in files:
                continue
            try:
                # import settings explicitly
                mod = import_module(root.replace('/', '.') + '.settings')
            except ImportError as ex:
                if re.search('No module named .*settings', str(ex)):
                    continue
                raise
            else:
                self.load_from_object(
                    mod, getattr(mod, '__NAMESPACE__', ns), mutable
                )

    def __str__(self):
        return '[%s][namespaces|%d]' % (self.name, len(self.namespaces))
    __repr__ = __str__


settings = Settings('global')
settings.add_watcher(configure_logging, ns='pymaid')
settings.add_watcher(configure_logging, ns='logging')
settings.load_from_object(defaults, ns='pymaid', mutable=False)
