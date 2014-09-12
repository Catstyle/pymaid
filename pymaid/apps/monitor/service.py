from __future__ import absolute_import

from .monitor_service_pb2 import MonitorService, HeartbearInfo


class MonitorServiceImpl(MonitorService):

    def get_heartbeat_info(self, controller, request, done):
        info = HeartbearInfo()
        info.need_heartbeat = self.channel.need_heartbeat
        if info.need_heartbeat:
            info.heartbeat_interval = self.channel.heartbeat_interval
        return info

    def notify_heartbeat(self, controller, request, done):
        controller.conn.clear_heartbeat_counter()
