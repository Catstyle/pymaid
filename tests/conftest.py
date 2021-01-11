import pymaid
import pytest


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
