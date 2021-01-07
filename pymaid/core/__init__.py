'''Pymaid is based on asyncio now.

And for better performance, it use uvloop as the event loop
'''
import asyncio
import socket

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import partial

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

run = asyncio.run
sleep = asyncio.sleep
get_event_loop = asyncio.get_event_loop
get_event_loop_policy = asyncio.get_event_loop_policy
get_running_loop = asyncio.get_running_loop


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
