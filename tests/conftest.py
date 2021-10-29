import os

import pymaid
import pytest

from pymaid.conf import defaults, settings
from pymaid.utils.logger import get_logger

logger = get_logger('pymaid')


@pytest.fixture
def event_loop():
    # as upgraded to pytest-asyncio == 0.14.0
    # it reset default event loop after every test
    # so, this is a workaround to use the loop as pymaid
    if pymaid.conf.settings.pymaid.get('EVENT_LOOP') == 'uvloop':
        import uvloop
        uvloop.install()
    loop = pymaid.get_event_loop_policy().new_event_loop()
    logger.warning(
        '[pymaid|run] [loop|%s][DEBUG|%s]',
        pymaid.conf.settings.pymaid.get('EVENT_LOOP'),
        pymaid.conf.settings.pymaid.DEBUG,
    )
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def housekeeper():
    # setup
    yield
    # teardown
    for name in os.environ.keys():
        if name.startswith('SETTING__'):
            os.environ.pop(name)
    settings.namespaces.clear()
    settings.load_from_object(defaults, ns='pymaid')
