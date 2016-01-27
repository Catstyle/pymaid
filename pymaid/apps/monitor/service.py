from .monitor_pb2 import MonitorService


class MonitorServiceImpl(MonitorService):

    def notify_heartbeat(self, controller, request, callback):
        controller.conn.clear_heartbeat_counter()
