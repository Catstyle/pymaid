from pymaid import backend
from pymaid.ext.middleware import BaseMiddleware

from .error import MonitorError


class MonitorMiddleware(BaseMiddleware):

    def __init__(self, heartbeat_interval, heartbeat_count):
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_count = heartbeat_count

    def on_connect(self, transport):
        transport.heartbeat_count = 0
        loop = backend.get_running_loop()

        def clear_heartbeat_counter():
            transport.heartbeat_count = 0
            transport.heartbeat_timer.cancel()
            transport.heartbeat_timer = loop.call_later(heartbeat_timeout)

        def heartbeat_timeout():
            transport.heartbeat_count += 1
            if transport.heartbeat_count >= self.heartbeat_count:
                transport.heartbeat_timer.cancel()
                transport.close(MonitorError.HeartbeatTimeout())

        transport.heartbeat_timer = loop.call_later(heartbeat_timeout)
        transport.clear_heartbeat_counter = clear_heartbeat_counter

    def on_close(self, transport):
        transport.heartbeat_timer.cancel()
        del transport.heartbeat_timer
        del transport.clear_heartbeat_counter
        del transport.heartbeat_count
