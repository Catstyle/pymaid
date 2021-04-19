# inspired by https://github.com/aio-libs/async-timeout

import os
import time

import pytest

import pymaid
from pymaid.utils.timeout import timeout, timeout_at


@pytest.mark.asyncio
async def test_timeout():
    canceled_raised = False

    async def long_running_task():
        try:
            await pymaid.sleep(10)
        except pymaid.CancelledError:
            nonlocal canceled_raised
            canceled_raised = True
            raise

    with pytest.raises(pymaid.TimeoutError):
        async with timeout(0.01) as t:
            await long_running_task()
            assert t._loop is pymaid.get_event_loop()
    assert canceled_raised, 'CancelledError was not raised'


@pytest.mark.asyncio
async def test_timeout_finish_in_time():
    async def long_running_task():
        await pymaid.sleep(0.01)
        return 'done'

    async with timeout(0.1):
        resp = await long_running_task()
    assert resp == 'done'


@pytest.mark.asyncio
async def test_timeout_disable():
    async def long_running_task():
        await pymaid.sleep(0.1)
        return 'done'

    loop = pymaid.get_event_loop()
    t0 = loop.time()
    async with timeout(None):
        resp = await long_running_task()
    assert resp == 'done'
    dt = loop.time() - t0
    assert 0.09 < dt < 0.13, dt


@pytest.mark.asyncio
async def test_timeout_is_none_no_schedule():
    async with timeout(None) as cm:
        assert cm.timeout_handler is None
        assert cm.deadline is None


def test_timeout_no_loop():
    with pytest.raises(RuntimeError, match='no running event loop'):
        timeout(None)


@pytest.mark.asyncio
async def test_timeout_zero():
    with pytest.raises(pymaid.TimeoutError):
        timeout(0)


@pytest.mark.asyncio
async def test_timeout_not_relevant_exception():
    await pymaid.sleep(0)
    with pytest.raises(KeyError):
        async with timeout(0.1):
            raise KeyError


@pytest.mark.asyncio
async def test_timeout_cancelled_error_is_not_converted_to_timeout():
    await pymaid.sleep(0)
    with pytest.raises(pymaid.CancelledError):
        async with timeout(0.001):
            raise pymaid.CancelledError


@pytest.mark.asyncio
async def test_timeout_blocking_loop():
    async def long_running_task():
        time.sleep(0.1)
        return 'done'

    async with timeout(0.01):
        result = await long_running_task()
    assert result == 'done'


@pytest.mark.asyncio
async def test_for_race_conditions():
    loop = pymaid.get_event_loop()
    fut = loop.create_future()
    loop.call_later(0.1, fut.set_result('done'))
    async with timeout(0.2):
        resp = await fut
    assert resp == 'done'


@pytest.mark.asyncio
async def test_timeout_time():
    foo_running = None
    loop = pymaid.get_event_loop()
    start = loop.time()
    with pytest.raises(pymaid.TimeoutError):
        async with timeout(0.1):
            foo_running = True
            try:
                await pymaid.sleep(0.2)
            finally:
                foo_running = False

    dt = loop.time() - start
    if not (0.09 < dt < 0.11) and os.environ.get('APPVEYOR'):
        pytest.xfail('appveyor sometimes is toooo sloooow')
    assert 0.09 < dt < 0.11
    assert not foo_running


@pytest.mark.asyncio
async def test_outer_coro_is_not_cancelled():

    has_timeout = False

    async def outer():
        nonlocal has_timeout
        try:
            async with timeout(0.001):
                await pymaid.sleep(1)
        except pymaid.TimeoutError:
            has_timeout = True

    task = pymaid.ensure_future(outer())
    await task
    assert has_timeout
    assert not task.cancelled()
    assert task.done()


@pytest.mark.asyncio
async def test_cancel_outer_coro():
    loop = pymaid.get_event_loop()
    fut = loop.create_future()

    async def outer():
        fut.set_result(None)
        await pymaid.sleep(1)

    task = pymaid.ensure_future(outer())
    await fut
    task.cancel()
    with pytest.raises(pymaid.CancelledError):
        await task
    assert task.cancelled()
    assert task.done()


@pytest.mark.asyncio
async def test_timeout_suppress_exception_chain():
    with pytest.raises(pymaid.TimeoutError) as ctx:
        async with timeout(0.01):
            await pymaid.sleep(10)
    assert not ctx.value.__suppress_context__


@pytest.mark.asyncio
async def test_timeout_expired():
    with pytest.raises(pymaid.TimeoutError):
        async with timeout(0.01) as cm:
            await pymaid.sleep(10)
    assert cm.expired


@pytest.mark.asyncio
async def test_timeout_inner_timeout_error():
    with pytest.raises(pymaid.TimeoutError):
        async with timeout(0.01) as cm:
            raise pymaid.TimeoutError
    assert not cm.expired


@pytest.mark.asyncio
async def test_timeout_inner_other_error():
    class MyError(RuntimeError):
        pass

    with pytest.raises(MyError):
        async with timeout(0.01) as cm:
            raise MyError
    assert not cm.expired


@pytest.mark.asyncio
async def test_timeout_at():
    loop = pymaid.get_event_loop()
    with pytest.raises(pymaid.TimeoutError):
        now = loop.time()
        async with timeout_at(now + 0.01) as cm:
            await pymaid.sleep(10)
    assert cm.expired


@pytest.mark.asyncio
async def test_timeout_at_not_fired():
    loop = pymaid.get_event_loop()
    now = loop.time()
    async with timeout_at(now + 1) as cm:
        await pymaid.sleep(0)
    assert not cm.expired


@pytest.mark.asyncio
async def test_expired_after_aborting():
    t = timeout(10)
    assert not t.expired
    t.abort()
    assert not t.expired


@pytest.mark.asyncio
async def test_abort_finished():
    async with timeout(10) as t:
        await pymaid.sleep(0)

    assert not t.expired
    with pytest.raises(RuntimeError, match='invalid state EXIT'):
        t.abort()


@pytest.mark.asyncio
async def test_expired_after_timeout():
    with pytest.raises(pymaid.TimeoutError):
        async with timeout(0.01) as t:
            assert not t.expired
            await pymaid.sleep(10)
    assert t.expired


@pytest.mark.asyncio
async def test_deadline():
    loop = pymaid.get_event_loop()
    t0 = loop.time()
    async with timeout(1) as cm:
        t1 = loop.time()
        assert t0 + 1 <= cm.deadline <= t1 + 1


@pytest.mark.asyncio
async def test_async_timeout():
    with pytest.raises(pymaid.TimeoutError):
        async with timeout(0.01) as cm:
            await pymaid.sleep(10)
    assert cm.expired


@pytest.mark.asyncio
async def test_async_no_timeout():
    async with timeout(1) as cm:
        await pymaid.sleep(0)
    assert not cm.expired


@pytest.mark.asyncio
async def test_shift_to():
    loop = pymaid.get_event_loop()
    t0 = loop.time()
    async with timeout(1) as cm:
        t1 = loop.time()
        assert t0 + 1 <= cm.deadline <= t1 + 1
        cm.shift_to(t1 + 1)
        assert t1 + 1 <= cm.deadline <= t1 + 1.001


@pytest.mark.asyncio
async def test_shift_by():
    loop = pymaid.get_event_loop()
    t0 = loop.time()
    async with timeout(1) as cm:
        t1 = loop.time()
        assert t0 + 1 <= cm.deadline <= t1 + 1
        cm.shift_by(1)
        assert t1 + 0.999 <= cm.deadline <= t1 + 1.001


@pytest.mark.asyncio
async def test_shift_by_negative_expired():
    async with timeout(1) as cm:
        with pytest.raises(pymaid.CancelledError):
            cm.shift_by(-1)


@pytest.mark.asyncio
async def test_shift_by_expired():
    async with timeout(0.01) as cm:
        with pytest.raises(pymaid.CancelledError):
            await pymaid.sleep(10)
        with pytest.raises(
            RuntimeError, match='cannot reschedule expired timeout'
        ):
            await cm.shift_by(10)


@pytest.mark.asyncio
async def test_shift_to_expired():
    loop = pymaid.get_event_loop()
    t0 = loop.time()
    async with timeout_at(t0 + 0.01) as cm:
        with pytest.raises(pymaid.CancelledError):
            await pymaid.sleep(10)
        with pytest.raises(
            RuntimeError, match='cannot reschedule expired timeout'
        ):
            await cm.shift_to(t0 + 10)


@pytest.mark.asyncio
async def test_shift_by_after_cm_exit():
    async with timeout(1) as cm:
        await pymaid.sleep(0)
    with pytest.raises(
        RuntimeError, match='cannot reschedule after exit from context manager'
    ):
        cm.shift_by(1)


@pytest.mark.asyncio
async def test_enter_twice():
    async with timeout(10) as t:
        await pymaid.sleep(0)

    with pytest.raises(RuntimeError, match='invalid state EXIT'):
        async with t:
            await pymaid.sleep(0)
