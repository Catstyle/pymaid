from __future__ import absolute_import

from collections import defaultdict
from functools import partial
from importlib import import_module
import os
import re
import sys

from ujson import loads

from pymaid.utils.logger import configure_logging, pymaid_logger_wrapper

from . import defaults


class Namespace(dict):

    def __dir__(self):
        return super(Namespace, self).__dir__() + list(self.keys())

    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if not self.get('__MUTABLE__', False):
            raise RuntimeError('settings namespace is immutable')
        if name in self:
            self[name] = value
        else:
            raise AttributeError(name)


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

        Fix: check __MUTABLE__ before setting settings
        """
        try:
            namespace = self.namespaces[ns]
        except KeyError:
            self.logger.warn(
                'set value: %s to key: %s, of unknown namespace: %s',
                value, key, ns,
            )
        if not namespace.get('__MUTABLE__', False):
            raise RuntimeError('[pymaid][settings][ns|%s] is immutable' % ns)
        setattr(namespace, key, value)

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
            self.logger.warn('[pymaid][settings][ns|%s] is immutable', ns)
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
        self.namespaces.setdefault(ns, Namespace()).update(data)
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

    def __getattr__(self, name):
        '''Implemented `settings.namespace.key` usage'''
        if name in self.namespaces:
            # cache
            ns = self.namespaces[name]
            setattr(self, name, ns)
            return ns
        raise AttributeError(name)

    def __dir__(self):
        return super(Settings, self).__dir__() + list(self.namespaces.keys())


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


def load_from_environment(prefix='SETTING__', raise_invalid_value=True):
    '''load *special formatted* env into settings

    format: {PREFIX}__{NAMESPACE}__{KEY}=VALUE
    PREFIX: pymaid settings
    NAMESPACE: namespace
    KEY: settings key name
    VALUE: type::value, type need to be builtin type,
        current are %s
        dict/list will be loaded using json.loads

    NOTE: when loaded, {NAMESPACE} will transform to lower case

    e.g.:
        export SETTING__PYMAID__DEBUG='bool::True'
        will result in below
        settings.set('DEBUG', True, ns='pymaid')
        settings.namespaces['pymaid']['DEBUG'] = True
    '''

    # cannot endswith ___
    # can only has one '__'
    if not re.match(r'[A-Z]+__$', prefix):
        raise ValueError(
            'prefix should be in the format of `NAME__`, got `%s`' % prefix
        )

    env_regex = re.compile(
        r'^%s[A-Z][A-Z_]+[A-Z]__[A-Z][A-Z_]+[A-Z]$' % prefix
    )
    data = {}
    for env, value in os.environ.items():
        # naive check
        if not env.startswith(prefix):
            continue
        if not env_regex.match(env):
            sys.stderr.write('wrong special formatted env `%s`\n' % env)
            continue

        env_ = env.split('__')
        if len(env_) != 3:
            sys.stderr.write('wrong special formatted env `%s`\n' % env)
            continue
        _, ns, key = env_

        value_ = value.split('::')
        if len(value_) != 2:
            err = (
                'get special formatted env `%s`, but wrong format value `%s`, '
                'should be in format of `type::value`\n' % (env, value)
            )
            if raise_invalid_value:
                raise ValueError(err)
            sys.stderr.write(err)
            continue

        t, val = value_
        if t not in transformer:
            err = (
                'unknown value type `%s` for env `%s=%s`, available `%s`\n' %
                (t, env, value, transformer.keys())
            )
            if raise_invalid_value:
                raise ValueError(err)
            sys.stderr.write(err)
            continue

        try:
            val = transformer[t](val)
        except (TypeError, ValueError):
            err = (
                'cannot transform value of `%s=%s`, check type and value\n' %
                (env, value)
            )
            if raise_invalid_value:
                raise ValueError(err)
            sys.stderr.write(err)
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
