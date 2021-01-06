import pytest
import uvloop


@pytest.fixture
def event_loop():
    loop = uvloop.Loop()
    yield loop
    loop.close()
