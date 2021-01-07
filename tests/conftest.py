import pymaid
import pytest


@pytest.fixture
def event_loop():
    loop = pymaid.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
