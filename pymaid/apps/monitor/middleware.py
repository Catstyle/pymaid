from pymaid.utils import timer
from pymaid.apps.middleware import BaseMiddleware

from .error import MonitorError


class MonitorMiddleware(BaseMiddleware):

    def __init__(self, heartbeat_interval, heartbeat_count):
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_count = heartbeat_count

    def on_connect(self, conn):
        conn.heartbeat_count = 0

        def clear_heartbeat_counter():
            conn.heartbeat_count = 0
            heartbeat_timer.again(heartbeat_timeout)

        def heartbeat_timeout():
            conn.heartbeat_count += 1
            if conn.heartbeat_count >= self.heartbeat_count:
                conn.heartbeat_timer.stop()
                conn.close(MonitorError.HeartbeatTimeout())

        heartbeat_timer = timer(0, self.heartbeat_interval)
        heartbeat_timer.again(heartbeat_timeout)
        conn.heartbeat_timer = heartbeat_timer
        conn.clear_heartbeat_counter = clear_heartbeat_counter

    def on_close(self, conn):
        conn.heartbeat_timer.stop()
        del conn.heartbeat_timer
        del conn.clear_heartbeat_counter
        del conn.heartbeat_count
