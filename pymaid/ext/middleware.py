from collections import defaultdict
from typing import List, Optional


class BaseMiddleware:
    '''Base class for Middleware.

    *NOTE*: all on_* methods will be treated as event callbacks, and will be cached in
        MiddlewareManager.events for faster dispatching.

    e.g.: on_connect/on_close are examples.
    '''

    def on_connect(self, conn):
        raise NotImplementedError()

    def on_close(self, conn):
        raise NotImplementedError()


class MiddlewareManager:

    def __init__(self, middlewares: Optional[List[BaseMiddleware]] = None):
        self.middlewares = []
        self.events = defaultdict(list)

        if middlewares:
            self.append_middlewares(middlewares)

    def append_middleware(self, middleware: BaseMiddleware):
        self.middlewares.append(middleware)

        for attr in dir(middleware):
            if attr.startswith('on_'):
                self.events[attr].append(getattr(middleware, attr))

    def append_middlewares(self, middlewares: List[BaseMiddleware]):
        for mw in middlewares:
            self.append_middleware(mw)

    def dispatch(self, event, *args, **kwargs):
        for callback in self.events.get(event, []):
            callback(*args, **kwargs)
