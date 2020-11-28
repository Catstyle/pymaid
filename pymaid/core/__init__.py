'''
pymaid is based on asyncio now, and for better performance, it use
uvloop as the event loop
'''
import uvloop

import asyncio  # noqa
import socket  # noqa

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor  # noqa
from functools import partial

uvloop.install()  # noqa


#
# event loop
#

run = asyncio.run
sleep = asyncio.sleep
get_event_loop = asyncio.get_event_loop
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


async def create_stream(transport_class, host, port, *, retry=3, **kwargs):
    return (await get_running_loop().create_connection(
        partial(transport_class, client_side=True), host, port, **kwargs
    ))[1]


async def create_datagram(transport_class, addr, **kwargs):
    return (await get_running_loop().create_datagram_endpoint(
        partial(transport_class, client_side=True), remote_addr=addr, **kwargs
    ))[1]


async def create_stream_server(transport_class, host, port, **kwargs):
    return await get_running_loop().create_server(
        transport_class, host, port, **kwargs
    )


async def create_datagram_server(transport_class, addr, **kwargs):
    return await get_running_loop().create_datagram_endpoint(
        transport_class, local_addr=addr, **kwargs
    )


async def create_unix_stream(transport_class, path, *, retry=3, **kwargs):
    return (await get_running_loop().create_unix_connection(
        partial(transport_class, client_side=True), path, **kwargs
    ))[1]


async def create_unix_datagram(transport_class, path, **kwargs):
    return (await get_running_loop().create_datagram_endpoint(
        partial(transport_class, client_side=True),
        remote_addr=path,
        family=socket.AF_UNIX,
        **kwargs
    ))[1]


async def create_unix_stream_server(transport_class, path, **kwargs):
    return await get_running_loop().create_unix_server(transport_class, path, **kwargs)


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


def run_in_thread(
    func, *, args=None, kwargs=None, executor=default_thread_executor,
):
    return wrap_future(executor.submit(func, *(args or ()), **(kwargs or {})))


def run_in_process(
    func, *, args=None, kwargs=None, executor=default_process_executor,
):
    return wrap_future(executor.submit(func, *(args or ()), **(kwargs or {})))


del asyncio, uvloop
