# inspired by https://github.com/aio-libs/async-timeout

import asyncio
import enum
from types import TracebackType
from typing import Optional, Type

from pymaid.core import current_task, get_running_loop


__all__ = ('timeout', 'timeout_at')


def timeout(delay: Optional[float]) -> 'Timeout':
    '''timeout context manager.

    Useful in cases when you want to apply timeout logic around block
    of code or in cases when asyncio.wait_for is not suitable. For example:

    >>> async with timeout(0.001):
    ...     async with aiohttp.get('https://github.com') as r:
    ...         await r.text()


    delay - value in seconds or None to disable timeout logic
    '''
    deadline = get_running_loop().time() + delay if delay is not None else None
    return Timeout(deadline)


def timeout_at(deadline: Optional[float]) -> 'Timeout':
    '''Schedule the timeout at absolute time.

    deadline arguments points on the time in the same clock system
    as loop.time().

    Please note: it is not POSIX time but a time with
    undefined starting base, e.g. the time of the system power on.

    >>> async with timeout_at(loop.time() + 10):
    ...     async with aiohttp.get('https://github.com') as r:
    ...         await r.text()


    '''
    return Timeout(deadline)


class State(enum.Enum):
    INIT = 'INIT'
    ENTER = 'ENTER'
    TIMEOUT = 'TIMEOUT'
    EXIT = 'EXIT'


class Timeout:
    # Internal class, please don't instantiate it directly
    # Use timeout() and timeout_at() public factories instead.
    #
    # Implementation note: `async with timeout()` is preferred
    # over `with timeout()`.
    # While technically the Timeout class implementation
    # doesn't need to be async at all,
    # the `async with` statement explicitly points that
    # the context manager should be used from async function context.
    #
    # This design allows to avoid many silly misusages.
    #
    # TimeoutError is raised immadiatelly when scheduled
    # if the deadline is passed.
    # The purpose is to time out as sson as possible
    # without waiting for the next await expression.

    __slots__ = ('deadline', 'loop', 'state', 'task', 'timeout_handler')

    def __init__(self, deadline: Optional[float]):
        self.loop = get_running_loop()
        self.task = current_task()
        self.state = State.INIT

        self.timeout_handler = None  # type: Optional[asyncio.Handle]
        if deadline is None:
            self.deadline = None  # type: Optional[float]
        else:
            self.shift_to(deadline)

    async def __aenter__(self) -> 'Timeout':
        if self.state != State.INIT:
            raise RuntimeError(f'invalid state {self.state.value}')
        self.state = State.ENTER
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> Optional[bool]:
        if exc_type is asyncio.CancelledError and self.state == State.TIMEOUT:
            self.timeout_handler = None
            raise asyncio.TimeoutError
        # timeout is not expired
        self.state = State.EXIT
        self._abort()
        return None

    @property
    def expired(self) -> bool:
        '''Is timeout expired during execution?'''
        return self.state == State.TIMEOUT

    def abort(self) -> None:
        '''Abort scheduled timeout if any.'''
        # cancel is maybe better name but
        # task.cancel() raises CancelledError in asyncio world.
        if self.state not in (State.INIT, State.ENTER):
            raise RuntimeError(f'invalid state {self.state.value}')
        self._abort()

    def _abort(self) -> None:
        if self.timeout_handler is not None:
            self.timeout_handler.cancel()
            self.timeout_handler = None

    def shift_by(self, delay: float) -> None:
        '''Advance timeout on delay seconds.

        The delay can be negative.
        '''
        self.shift_to(self.loop.time() + delay)

    def shift_to(self, deadline: float) -> None:
        '''Set timeout deadline to the absolute time.

        If new deadline is in the past, the timeout is raised immediately.
        '''
        if self.state == State.EXIT:
            raise RuntimeError(
                'cannot reschedule after exit from context manager'
            )
        if self.state == State.TIMEOUT:
            raise RuntimeError('cannot reschedule expired timeout')
        if self.timeout_handler is not None:
            self.timeout_handler.cancel()
        self.deadline = deadline
        now = self.loop.time()
        if deadline <= now:
            self.timeout_handler = None
            if self.state == State.INIT:
                raise asyncio.TimeoutError
            else:
                # state is ENTER
                raise asyncio.CancelledError
        self.timeout_handler = self.loop.call_at(
            deadline, self.on_timeout, self.task
        )

    def on_timeout(self, task: 'asyncio.Task[None]') -> None:
        task.cancel()
        self.state = State.TIMEOUT
