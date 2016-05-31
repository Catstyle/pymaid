from .monitor_pb2 import MonitorService

from pymaid.utils import logger_wrapper, implall, trace_service


@trace_service
@logger_wrapper
@implall
class MonitorServiceImpl(MonitorService):

    def NotifyHeartbeat(self, controller, request, done):
        controller.conn.clear_heartbeat_counter()
        done()
