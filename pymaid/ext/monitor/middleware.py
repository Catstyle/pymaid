from pymaid.core import get_running_loop
from pymaid.ext.middleware import BaseMiddleware

from .error import MonitorError


class HeartbeatMiddleware(BaseMiddleware):

    def __init__(self, heartbeat_interval: int, heartbeat_count: int):
        '''
        :param heartbeat_interval: heartbeat checking interval in seconds.
        :param heartbeat_count: heartbeat checking count before marking as heartbeat timeout.
        '''
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_count = heartbeat_count

    def on_connect(self, channel, transport):
        transport.heartbeat_count = 0
        loop = get_running_loop()

        def clear_heartbeat_counter():
            transport.heartbeat_count = 0
            transport.heartbeat_timer.cancel()
            transport.heartbeat_timer = loop.call_later(self.heartbeat_timer, heartbeat_timeout)

        def heartbeat_timeout():
            transport.heartbeat_count += 1
            if transport.heartbeat_count >= self.heartbeat_count:
                transport.heartbeat_timer.cancel()
                transport.close(MonitorError.HeartbeatTimeout())

        transport.heartbeat_timer = loop.call_later(self.heartbeat_interval, heartbeat_timeout)
        transport.clear_heartbeat_counter = clear_heartbeat_counter

    def on_close(self, channel, transport):
        transport.heartbeat_timer.cancel()
        del transport.heartbeat_timer
        del transport.clear_heartbeat_counter
        del transport.heartbeat_count
