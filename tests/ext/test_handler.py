from unittest import mock

import pytest

from pymaid.core import sleep
from pymaid.ext.handler import Handler, SerialHandler, ParallelHandler
from pymaid.utils.logger import get_logger

logger = get_logger('pymaid')


def inc(d, delta):
    d['count'] += delta
    d['deltas'].append(delta)


async def async_inc(d, delta):
    d['count'] += delta
    d['deltas'].append(delta)


def test_cannot_init_abc_handler():
    with pytest.raises(TypeError):
        Handler()


@pytest.mark.asyncio
async def test_handle_serial_normal_task():
    handler = SerialHandler()
    d = {'count': 0, 'deltas': []}

    async with handler:
        handler.submit(inc, d, 1)
        handler.submit(inc, d, 2)
        handler.submit(inc, d, 3)

    assert d['count'] == 6
    assert d['deltas'] == [1, 2, 3]


@pytest.mark.asyncio
async def test_handle_serial_async_task():
    handler = SerialHandler()
    d = {'count': 0, 'deltas': []}

    async with handler:
        handler.submit(async_inc, d, 1)
        handler.submit(async_inc, d, 2)
        handler.submit(async_inc, d, 3)

    assert d['count'] == 6
    assert d['deltas'] == [1, 2, 3]


@pytest.mark.asyncio
async def test_handle_serial_mix_task():
    handler = SerialHandler()
    d = {'count': 0, 'deltas': []}

    async with handler:
        handler.submit(async_inc, d, 1)
        handler.submit(inc, d, 2)
        handler.submit(sleep, 0.0001)
        handler.submit(async_inc, d, 3)
        await sleep(0.00001)
        handler.submit(inc, d, 4)

    assert d['count'] == 10
    assert d['deltas'] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_handle_parallel_normal_task():
    handler = ParallelHandler()
    d = {'count': 0, 'deltas': []}

    async with handler:
        handler.submit(inc, d, 1)
        handler.submit(inc, d, 2)
        handler.submit(inc, d, 3)

    assert d['count'] == 6
    assert sorted(d['deltas']) == [1, 2, 3]


@pytest.mark.asyncio
async def test_handle_parallel_async_task():
    handler = ParallelHandler()
    d = {'count': 0, 'deltas': []}

    async with handler:
        handler.submit(inc, d, 1)
        handler.submit(inc, d, 2)
        handler.submit(inc, d, 3)

    assert d['count'] == 6
    assert sorted(d['deltas']) == [1, 2, 3]


@pytest.mark.asyncio
async def test_handle_parallel_mix_task():
    handler = ParallelHandler()
    d = {'count': 0, 'deltas': []}

    async with handler:
        handler.submit(async_inc, d, 1)
        handler.submit(inc, d, 2)
        handler.submit(sleep, 0.0001)
        handler.submit(async_inc, d, 3)
        await sleep(0.00001)
        handler.submit(inc, d, 4)

    assert d['count'] == 10
    assert sorted(d['deltas']) == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_on_close():
    m = mock.MagicMock()
    async with ParallelHandler(on_close=[m]):
        ...
    assert m.call_count == 1

    m = mock.MagicMock()
    async with ParallelHandler(on_close=[m, m]):
        ...
    assert m.call_count == 2


@pytest.mark.asyncio
async def test_error_handler():
    d = {'error': 0}

    async def record(exc):
        d['error'] += 1

    async with ParallelHandler(error_handler=record) as handler:
        handler.submit(lambda: 1 / 0)

    assert d['error'] == 1


@pytest.mark.asyncio
async def test_serial_handler_close_on_exception():
    d = {'count': 0, 'deltas': []}

    async with SerialHandler(close_on_exception=True) as handler:
        handler.submit(lambda: 1 / 0)
        handler.submit(inc, d, 1)

    assert d['count'] == 0
    assert d['deltas'] == []


@pytest.mark.asyncio
async def test_parallel_handler_close_on_exception():
    d = {'count': 0, 'deltas': []}

    async with ParallelHandler(
        close_on_exception=True, concurrency=1,
    ) as handler:
        handler.submit(lambda: 1 / 0)
        handler.submit(inc, d, 1)

    assert d['count'] == 0
    assert d['deltas'] == []
