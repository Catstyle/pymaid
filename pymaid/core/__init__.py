'''Pymaid is based on asyncio now.

And for better performance, it use uvloop as the event loop
'''
import asyncio
import signal
import socket

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import partial

from pymaid.utils.logger import get_logger

logger = get_logger('pymaid')

__all__ = (
    'run',
    'sleep',
    'get_event_loop',
    'get_event_loop_policy',
    'get_running_loop',

    'create_task',
    'current_task',
    'all_tasks',
    'wait_for',
    'wait',
    'gather',
    'Task',
    'TimeoutError',
    'CancelledError',
    'Future',
    'Event',
    'Semaphore',

    'Queue',
    'LifoQueue',
    'PriorityQueue',
    'QueueFull',
    'QueueEmpty',

    'create_stream',
    'create_datagram',
    'create_stream_server',
    'create_datagram_server',
    'create_unix_stream',
    'create_unix_stream_server',

    'iscoroutine',
    'iscoroutinefunction',
    'ensure_future',
    'wrap_future',
    'run_in_threadpool',
    'run_in_processpool',
)


#
# event loop
#

asyncio_run = asyncio.run
sleep = asyncio.sleep
get_event_loop = asyncio.get_event_loop
get_event_loop_policy = asyncio.get_event_loop_policy
get_running_loop = asyncio.get_running_loop


async def with_context(coro):
    get_running_loop().add_signal_handler(signal.SIGINT, sig_interrupt)
    get_running_loop().add_signal_handler(signal.SIGTERM, sig_interrupt)
    await coro


def sig_interrupt():
    logger.info('[pymaid] receive interrupt/terminate signal')
    for task in all_tasks():
        task.cancel()


def run(main, *, args=None, kwargs=None, debug=None):
    from pymaid.conf import settings
    if settings.get('EVENT_LOOP', ns='pymaid') == 'uvloop':
        import uvloop
        uvloop.install()
    debug = debug if debug is not None else settings.pymaid.DEBUG
    logger.warning(
        '[pymaid|run] [loop|%s][DEBUG|%s]',
        get_event_loop_policy().__class__.__name__,
        debug,
    )

    if iscoroutinefunction(main):
        main = main(*(args or ()), **(kwargs or {}))
    try:
        asyncio_run(with_context(main), debug=debug)
    except (SystemExit, KeyboardInterrupt):
        pass


#
# tasks
#

create_task = asyncio.create_task
current_task = asyncio.current_task
all_tasks = asyncio.all_tasks

wait_for = asyncio.wait_for
wait = asyncio.wait
gather = asyncio.gather

Task = asyncio.Task

TimeoutError = asyncio.TimeoutError
CancelledError = asyncio.CancelledError

Future = asyncio.Future
Event = asyncio.Event
Semaphore = asyncio.Semaphore


#
# queue
#

Queue = asyncio.Queue
LifoQueue = asyncio.LifoQueue
PriorityQueue = asyncio.PriorityQueue
QueueFull = asyncio.QueueFull
QueueEmpty = asyncio.QueueEmpty


#
# network
#

BaseTransport = asyncio.BaseTransport
BaseProtocol = asyncio.BaseProtocol


async def create_stream(transport_class, host, port, **kwargs):
    return (await get_running_loop().create_connection(
        partial(transport_class, initiative=True), host, port, **kwargs
    ))[1]


async def create_datagram(transport_class, addr, **kwargs):
    return (await get_running_loop().create_datagram_endpoint(
        partial(transport_class, initiative=True), remote_addr=addr, **kwargs
    ))[1]


async def create_stream_server(transport_class, host, port, **kwargs):
    return await get_running_loop().create_server(
        transport_class, host, port, **kwargs
    )


async def create_datagram_server(transport_class, addr, **kwargs):
    return await get_running_loop().create_datagram_endpoint(
        transport_class, local_addr=addr, **kwargs
    )


async def create_unix_stream(transport_class, path, **kwargs):
    return (await get_running_loop().create_unix_connection(
        partial(transport_class, initiative=True), path, **kwargs
    ))[1]


async def create_unix_datagram(transport_class, path, **kwargs):
    return (await get_running_loop().create_datagram_endpoint(
        partial(transport_class, initiative=True),
        remote_addr=path,
        family=socket.AF_UNIX,
        **kwargs
    ))[1]


async def create_unix_stream_server(transport_class, path, **kwargs):
    return await get_running_loop().create_unix_server(
        transport_class, path, **kwargs
    )


async def getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return await run_in_threadpool(
        socket.getaddrinfo, args=(host, port, family, type, proto, flags),
    )


# unix domain socket not support datagram

# async def create_unix_datagram_server(protocol, path, **kwargs):
#     loop = get_running_loop()
#     return await loop.create_datagram_endpoint(
#         protocol, local_addr=path, family=socket.AF_UNIX, **kwargs
#     )


#
# utils
#

iscoroutine = asyncio.iscoroutine
iscoroutinefunction = asyncio.iscoroutinefunction
ensure_future = asyncio.ensure_future
wrap_future = asyncio.futures.wrap_future


# executor

default_thread_executor = ThreadPoolExecutor()
default_process_executor = ProcessPoolExecutor()


def run_in_threadpool(
    func, *, args=None, kwargs=None, executor=default_thread_executor,
):
    return wrap_future(executor.submit(func, *(args or ()), **(kwargs or {})))


def run_in_processpool(
    func, *, args=None, kwargs=None, executor=default_process_executor,
):
    return wrap_future(executor.submit(func, *(args or ()), **(kwargs or {})))


del asyncio
