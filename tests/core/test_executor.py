import pytest

from pymaid.core import run_in_thread, run_in_process


def sum_int(a: int, b: int) -> int:
    return a + b


@pytest.mark.asyncio
async def test_run_in_thread():
    assert await run_in_thread(sum_int, args=(1, 2)) == 3
    assert await run_in_thread(sum_int, kwargs={'a': 1, 'b': 2}) == 3


@pytest.mark.asyncio
async def test_run_in_process():
    assert await run_in_process(sum_int, args=(1, 2)) == 3
    assert await run_in_process(sum_int, kwargs={'a': 1, 'b': 2}) == 3
