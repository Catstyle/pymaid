import os
from unittest import TestCase

from pymaid.conf import defaults
from pymaid.conf.settings import settings, load_from_environment


class SettingsTest(TestCase):

    def setUp(self):
        global settings
        settings.namespaces.clear()
        settings.load_from_object(defaults, ns='pymaid')

        self.other_namespace = {
            '__NAMESPACE__': 'other',
            '__MUTABLE__': False,
            'key': 1,
            'KEY': 2,
        }

    def test_get(self):
        assert settings.get('DEBUG', ns='pymaid') == defaults.DEBUG
        assert settings.get('NOT_EXIST', default='what') == 'what'

        settings.load_from_object(self.other_namespace)
        assert settings.get('KEY', ns='other') == self.other_namespace['KEY']
        # only upper key will be treated as settings
        assert settings.get('key', ns='other') is None

    def test_set(self):
        assert settings.get('MAX_TASKS', ns='pymaid') == defaults.MAX_TASKS
        settings.set('MAX_TASKS', defaults.MAX_TASKS + 1, ns='pymaid')
        assert settings.get('MAX_TASKS', ns='pymaid') != defaults.MAX_TASKS
        assert settings.get('MAX_TASKS', ns='pymaid') == defaults.MAX_TASKS + 1

        settings.load_from_object(self.other_namespace)
        assert settings.get('KEY', ns='other') == self.other_namespace['KEY']
        # cannot set immutable settings
        with self.assertRaises(RuntimeError):
            settings.set('KEY', 3, ns='other')

        # cannot set not exist settings
        with self.assertRaises(AttributeError):
            settings.set('NOT_EXIST', 1, ns='pymaid')

    def test_load_env(self):
        assert settings.get('MAX_TASKS', ns='pymaid') == defaults.MAX_TASKS
        assert settings.get('NOT_EXIST', default='what') == 'what'

        os.environ['SETTING__PYMAID__NOT_EXIST'] = 'str::noway'
        os.environ['SETTING__COMMON__NOT_EXIST'] = 'bytes::noway'
        os.environ['SETTING__PYMAID__MAX_TASKS'] = 'int::128'
        os.environ['SETTING__PYMAID__FLOAT'] = 'float::5.13543512414351235'
        os.environ['SETTING__PYMAID__BOOL'] = 'bool::False'
        os.environ['SETTING__PYMAID__DICT'] = 'dict::{"age": 18}'
        os.environ['SETTING__PYMAID__LIST'] = 'list::[1, 2, 3]'
        load_from_environment(prefix='SETTING__')

        assert settings.get('NOT_EXIST', ns='pymaid') == 'noway'
        assert settings.get('NOT_EXIST', default='what') == b'noway'
        assert settings.get('MAX_TASKS', ns='pymaid') == 128
        assert abs(settings.get('FLOAT', ns='pymaid') - 5.13543512414351235) < 1e-6  # noqa
        assert settings.get('BOOL', ns='pymaid') is False
        assert settings.get('DICT', ns='pymaid') == {'age': 18}
        assert settings.get('LIST', ns='pymaid') == [1, 2, 3]

    def test_load_env_bad_cases(self):
        # wrong prefix
        os.environ.clear()
        settings.namespaces.clear()

        os.environ['SETTING__PYMAID__LIST'] = 'list::[1, 2, 3]'
        with self.assertRaises(ValueError):
            load_from_environment(prefix='SETTING_')
        assert settings.get('LIST', ns='pymaid') is None
        assert not settings.namespaces

        os.environ.clear()
        with self.assertRaises(ValueError):
            load_from_environment(prefix='SETTING___')
        assert settings.get('LIST', ns='pymaid') is None
        assert not settings.namespaces

        # wrong namespace
        os.environ['SETTING___PYMAID__LIST'] = 'list::[1, 2, 3]'
        load_from_environment(prefix='SETTING__')
        assert settings.get('LIST', ns='pymaid') is None
        assert not settings.namespaces

        # wrong key
        os.environ['SETTING__PYMAID___LIST'] = 'list::[1, 2, 3]'
        load_from_environment(prefix='SETTING__')
        assert settings.get('LIST', ns='pymaid') is None
        assert not settings.namespaces

        # wrong value format
        os.environ['SETTING__PYMAID__LIST'] = '[1, 2, 3]'
        with self.assertRaises(ValueError):
            load_from_environment(prefix='SETTING__')
        assert settings.get('LIST', ns='pymaid') is None
        assert not settings.namespaces

        os.environ['SETTING__PYMAID__LIST'] = 'list:[1, 2, 3]'
        with self.assertRaises(ValueError):
            load_from_environment(prefix='SETTING__')
        assert settings.get('LIST', ns='pymaid') is None
        assert not settings.namespaces

        # wrong value type
        os.environ['SETTING__PYMAID__LIST'] = 'what_type::[1, 2, 3]'
        with self.assertRaises(ValueError):
            load_from_environment(prefix='SETTING__')
        assert settings.get('LIST', ns='pymaid') is None
        assert not settings.namespaces

        # wrong type::value
        os.environ['SETTING__PYMAID__LIST'] = 'int::[1, 2, 3]'
        with self.assertRaises(ValueError):
            load_from_environment(prefix='SETTING__')
        assert settings.get('LIST', ns='pymaid') is None
        assert not settings.namespaces

    def test_dot_get(self):
        assert settings.pymaid.DEBUG == defaults.DEBUG

        # not exists namespace
        with self.assertRaises(AttributeError):
            settings.what

        # not exists key
        with self.assertRaises(AttributeError):
            settings.pymaid.what

    def test_dot_set(self):
        assert settings.pymaid.MAX_TASKS == defaults.MAX_TASKS
        settings.pymaid.MAX_TASKS += 1
        assert settings.pymaid.MAX_TASKS == defaults.MAX_TASKS + 1

        # cannot set not exist
        with self.assertRaises(AttributeError):
            settings.pymaid.NOT_EXIST = 1

        settings.load_from_object(self.other_namespace)
        # cannot set immutable
        with self.assertRaises(RuntimeError):
            settings.other.KEY = 1
