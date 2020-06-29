import os
from unittest import TestCase

from pymaid.conf import defaults
from pymaid.conf.settings import settings, load_from_environment


class SettingsTest(TestCase):

    def setUp(self):
        global settings
        settings.namespaces.clear()
        settings.load_from_object(defaults, ns='pymaid')

    def test_get(self):
        assert settings.get('DEBUG', ns='pymaid') == defaults.DEBUG
        assert settings.get('NOT_EXIST', default='what') == 'what'

    def test_set(self):
        assert settings.get('MAX_TASKS', ns='pymaid') == defaults.MAX_TASKS
        settings.set('MAX_TASKS', defaults.MAX_TASKS + 1, ns='pymaid')
        assert settings.get('MAX_TASKS', ns='pymaid') != defaults.MAX_TASKS

    def test_load_env(self):
        assert settings.get('MAX_TASKS', ns='pymaid') == defaults.MAX_TASKS
        assert settings.get('NOT_EXIST', default='what') == 'what'

        os.environ['PS__PYMAID__NOT_EXIST'] = 'str::noway'
        os.environ['PS__COMMON__NOT_EXIST'] = 'bytes::noway'
        os.environ['PS__PYMAID__MAX_TASKS'] = 'int::128'
        os.environ['PS__PYMAID__FLOAT'] = 'float::5.13543512414351235'
        os.environ['PS__PYMAID__BOOL'] = 'bool::False'
        os.environ['PS__PYMAID__DICT'] = 'dict::{"age": 18}'
        os.environ['PS__PYMAID__LIST'] = 'list::[1, 2, 3]'
        load_from_environment()

        assert settings.get('NOT_EXIST', ns='pymaid') == 'noway'
        assert settings.get('NOT_EXIST', default='what') == b'noway'
        assert settings.get('MAX_TASKS', ns='pymaid') == 128
        assert abs(settings.get('FLOAT', ns='pymaid') - 5.13543512414351235) < 1e-6  # noqa
        assert settings.get('BOOL', ns='pymaid') is False
        assert settings.get('DICT', ns='pymaid') == {'age': 18}
        assert settings.get('LIST', ns='pymaid') == [1, 2, 3]
