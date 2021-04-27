import os

import pymaid
import pytest

from pymaid.conf import defaults, settings


@pytest.fixture
def event_loop():
    # as upgraded to pytest-asyncio == 0.14.0
    # it reset default event loop after every test
    # so, this is a workaround to use the loop as pymaid
    if not pymaid.conf.settings.pymaid.get('NO_UVLOOP'):
        import uvloop
        uvloop.install()
    loop = pymaid.get_event_loop_policy().new_event_loop()
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
