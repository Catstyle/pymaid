import time

import pytest

from pymaid.core import run_in_threadpool, run_in_processpool


def sum_int(a: int, b: int) -> int:
    return a + b


def sleep(seconds):
    time.sleep(seconds)
    return time.time_ns()


@pytest.mark.asyncio
async def test_run_in_threadpool():
    assert await run_in_threadpool(sum_int, args=(1, 2)) == 3
    assert await run_in_threadpool(sum_int, kwargs={'a': 1, 'b': 2}) == 3

    now = time.time_ns()
    f1 = run_in_threadpool(sleep, args=(0.1,))
    f2 = run_in_threadpool(sleep, args=(0.1,))
    ts = time.time_ns()

    t1 = await f1
    t2 = await f2
    assert t1 > now + 0.1
    assert t2 > now + 0.1
    assert ts > now
    assert ts < t1
    assert ts < t2


@pytest.mark.asyncio
async def test_run_in_processpool():
    assert await run_in_processpool(sum_int, args=(1, 2)) == 3
    assert await run_in_processpool(sum_int, kwargs={'a': 1, 'b': 2}) == 3

    now = time.time_ns()
    f1 = run_in_processpool(sleep, args=(0.1,))
    f2 = run_in_processpool(sleep, args=(0.1,))
    ts = time.time_ns()

    t1 = await f1
    t2 = await f2
    assert t1 > now + 0.1
    assert t2 > now + 0.1
    assert ts > now
    assert ts < t1
    assert ts < t2
