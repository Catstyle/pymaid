from contextlib import AsyncExitStack, ExitStack
from functools import wraps
from sys import _getframe as getframe

from pymaid.core import iscoroutinefunction

from .logger import logger_wrapper

__all__ = ['ObjectManager', 'get_ipaddress']


@logger_wrapper
class ObjectManager(object):

    def __init__(self, name):
        self.name = name
        self.objects = {}

    def add(self, pk, obj):
        self.logger.info('[%s][add|%r][%s]', self.name, pk, obj)
        assert pk not in self.objects, pk
        self.objects[pk] = obj
        obj._manager = self

    def has(self, pk):
        return pk in self.objects

    def get(self, pk):
        assert pk in self.objects, pk
        return self.objects[pk]

    def remove(self, pk):
        self.logger.info('[%s][remove|%r]', self.name, pk)
        assert pk in self.objects, pk
        obj = self.objects.pop(pk)
        obj._manager = None
        return obj


def get_ipaddress(ifname):
    import socket
    import struct
    import fcntl
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(
        fcntl.ioctl(
            s.fileno(), 0x8915, struct.pack('256s', ifname[:15])
        )[20:24]
    )


def listify(obj):
    if obj is None:
        return []
    return obj if isinstance(obj, (tuple, list)) else [obj]


def with_defer(func):
    '''Used to enable defer

    For example:

    @with_defer
    def func1():
        defer(print, 'done func1')

    if use with multiple decorators, put it in the top

    @with_defer
    @decorator2
    @decorator3
    def func2():
        defer(print, 'done func2')

    it will also automatically detect async function

    @with_defer
    async def func1():
        defer(coroutinefunction)
        defer(print, 'done func1')

    if use with multiple decorators, put it in the top

    @with_defer
    @decorator2
    @decorator3
    async def func2():
        defer(coroutinefunction)
        defer(print, 'done func2')
    '''
    if iscoroutinefunction(func):
        @wraps(func)
        async def _(*args, **kwargs):
            is_async = True  # noqa, used by defer below
            async with AsyncExitStack() as __stack__:  # noqa, used by defer below
                return await func(*args, **kwargs)
        return _
    else:
        @wraps(func)
        def _(*args, **kwargs):
            is_async = False  # noqa, used by defer below
            with ExitStack() as __stack__:  # noqa, used by defer below
                return func(*args, **kwargs)
        return _


def defer(func, *args, **kwargs):
    '''Register a callback to be called when exit a scope.

    The callbacks are executed in LIFO order.

    If a callback raises an Exception, it will be reraised after all
    callbacks are executed.

    If multiple callbacks raise Exceptions, it will chain the exceptions
    tracebacks and you will see output like:
        ...
        *During handling of the above exception, another exception occurred:*
        ...
        *During handling of the above exception, another exception occurred:*
        ...
    '''
    f = getframe(2)
    if '__stack__' not in f.f_locals:
        raise RuntimeError(
            'calling scope is missing the with_defer decorator, '
            'nor with_defer decorator is not the innermost one'
        )
    st = f.f_locals['__stack__']
    if iscoroutinefunction(func):
        if not f.f_locals['is_async']:
            raise ValueError(
                'defer coroutinefunction required within coroutinefunction'
            )
        st.push_async_callback(func, *args, **kwargs)
    elif callable(func):
        st.callback(func, *args, **kwargs)
    else:
        raise TypeError(f'a callable is required, got {func}')


del logger_wrapper
