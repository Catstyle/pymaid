from __future__ import absolute_import

from collections import defaultdict
from functools import partial
from importlib import import_module
import os
import re

from ujson import loads

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
        '''Return specified config value in local namespaces cache.

        This method will not block and return default value if key not exists.
        User should initiate settings manually by calling `load_from_*` apis.
        '''
        try:
            return self.namespaces[ns][key]
        except KeyError:
            return default

    def set(self, key, value, ns='common'):
        """Update specified config value in local namespaces cache.

        This method will not block and *will not* update remote settings,
        this change will be discarded after destory this process.
        """
        try:
            self.namespaces[ns][key] = value
        except KeyError:
            self.logger.warn(
                'set value: %s to key: %s, of unknown namespace: %s',
                value, key, ns,
            )

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
settings.load_from_object(defaults, ns='pymaid')


transformer = {
    'str': str,
    'bytes': partial(bytes, encoding='utf-8'),
    'int': partial(int, base=10),
    'float': float,
    'bool': lambda x: False if x in ('False', 'false') else True,
    'dict': loads,
    'list': loads,
}


def load_from_environment():
    '''load *special formatted* env into settings

    format: PS__NS__KEY=VALUE
    PS: pymaid settings
    NS: namespace
    KEY: settings key name
    VALUE: type::value, type need to be builtin type,
        current are %s
        dict/list will be loaded using json.loads

    NOTE: when loaded, NS will transform to lower case

    e.g.: export PS__PYMAID__DEBUG='bool::True'
    '''

    import sys
    data = {}
    for env, value in os.environ.items():
        # naive check
        if not env.startswith('PS__'):
            continue

        env_ = env.split('__')
        if len(env_) != 3:
            sys.stderr.write('wrong special formatted env %s\n' % env)
            continue
        _, ns, key = env_

        value_ = value.split('::')
        if len(value_) != 2:
            sys.stderr.write(
                'get special formatted env %s, but wrong format value %s\n' % (
                    env, value
                )
            )
            continue

        t, val = value_
        if t not in transformer:
            sys.stderr.write(
                'unknown value type %s for env %s=%s\n' % (t, env, value)
            )
            continue

        try:
            val = transformer[t](val)
        except (TypeError, ValueError):
            sys.stderr.write(
                'cannot transform value of %s=%s\n' % (env, value)
            )
            continue

        # now we successfully get special env=value
        ns_data = data.setdefault(ns.lower(), {})
        ns_data[key] = val
    sys.stderr.flush()

    for ns, obj in data.items():
        settings.load_from_object(obj, ns=ns)


load_from_environment.__doc__ = (
    load_from_environment.__doc__ % list(transformer.keys())
)
