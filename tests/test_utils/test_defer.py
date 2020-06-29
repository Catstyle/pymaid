from functools import wraps
from unittest import mock

import pytest

from pymaid.core import iscoroutinefunction
from pymaid.utils.functional import with_defer, defer


def not_wrapped(func):
    return func


def wrapped(func):
    if iscoroutinefunction(func):
        @wraps(func)
        async def _(*args, **kwargs):
            return await func(*args, **kwargs)
        return _
    else:
        @wraps(func)
        def _(*args, **kwargs):
            return func(*args, **kwargs)
        return _


def test_defer():
    m = mock.Mock()

    @with_defer
    def func():
        defer(m, 'called by defer')

    func()
    m.assert_called_once_with('called by defer')

    m = mock.Mock()

    @with_defer
    def func(count):
        for idx in range(count):
            defer(m, idx)

    func(10)
    assert m.call_count == 10
    args = [c.args[0] for c in m.call_args_list]
    assert args == [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]


@pytest.mark.asyncio
async def test_defer_async():
    am = mock.AsyncMock()

    @with_defer
    async def func():
        defer(am, 'called by defer')

    await func()
    am.assert_called_once_with('called by defer')

    # async and sync comb
    am = mock.AsyncMock()
    m = mock.Mock()

    @with_defer
    async def func(count):
        for idx in range(count):
            defer(am, idx)
        defer(m, 'called by defer')

    await func(10)
    assert am.call_count == 10
    args = [c.args[0] for c in am.call_args_list]
    assert args == [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    m.assert_called_once_with('called by defer')


def test_no_with_defer():
    def func():
        defer(print, 'should not happen')

    # no decorator
    with pytest.raises(RuntimeError):
        func()


def test_sync_function_defer_async():
    am = mock.AsyncMock()

    @with_defer
    def func():
        defer(am, 'called by defer')

    # sync function but defer async
    with pytest.raises(ValueError):
        func()


@pytest.mark.asyncio
async def test_defer_not_callable():
    @with_defer
    def func():
        defer(1, 'called by defer')

    # sync function but defer not callable
    with pytest.raises(TypeError):
        func()

    @with_defer
    async def func():
        defer(1, 'called by defer')

    # async function but def not callable
    with pytest.raises(TypeError):
        await func()


@pytest.mark.asyncio
async def test_invalid_defer_scope():
    m = mock.Mock()

    @with_defer
    def func():
        def inner():
            defer(m, 'called by defer')
        inner()

    # defer from inner
    with pytest.raises(RuntimeError):
        func()

    am = mock.AsyncMock()

    @with_defer
    async def func():
        def inner():
            defer(am, 'called by defer')
        inner()

    # defer from inner
    with pytest.raises(RuntimeError):
        await func()


@pytest.mark.asyncio
async def test_multiple_decorators():

    m = mock.Mock()

    @not_wrapped
    @with_defer
    def func():
        defer(m, 'called by defer')
    func()
    m.assert_called_once_with('called by defer')

    # NOTICE, if decorator donot wraps the function calling, its order does not matter
    m = mock.Mock()

    @with_defer
    @not_wrapped
    def func():
        defer(m, 'called by defer')
    func()
    m.assert_called_once_with('called by defer')

    m = mock.Mock()

    @wrapped
    @with_defer
    def func():
        defer(m, 'called by defer')
    func()
    m.assert_called_once_with('called by defer')

    am = mock.Mock()

    @not_wrapped
    @with_defer
    async def func():
        defer(am, 'called by defer')
    await func()
    am.assert_called_once_with('called by defer')

    # NOTICE, if a decorator donot wraps the function calling, its order does not matter
    am = mock.Mock()

    @with_defer
    @not_wrapped
    async def func():
        defer(am, 'called by defer')
    await func()
    am.assert_called_once_with('called by defer')

    am = mock.Mock()

    @wrapped
    @with_defer
    async def func():
        defer(am, 'called by defer')
    await func()
    am.assert_called_once_with('called by defer')


@pytest.mark.asyncio
async def test_multiple_decorators_invalid_usage():
    m = mock.Mock()

    @with_defer
    @wrapped
    def func():
        defer(m, 'called by defer')

    # with_defer not the innermost one
    with pytest.raises(RuntimeError):
        func()

    am = mock.Mock()

    @with_defer
    @wrapped
    async def func():
        defer(am, 'called by defer')

    # with_defer not the innermost one
    with pytest.raises(RuntimeError):
        await func()
