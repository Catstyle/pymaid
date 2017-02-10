from pymaid.utils import implall

from .monitor_pb2 import MonitorService


@implall
class MonitorServiceImpl(MonitorService):

    def NotifyHeartbeat(self, controller, request, done):
        if not controller.conn.is_closed:
            controller.conn.clear_heartbeat_counter()
        done()
