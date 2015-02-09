from __future__ import absolute_import

from .monitor_pb2 import MonitorService, HeartbeatInfo


class MonitorServiceImpl(MonitorService):

    def get_heartbeat_info(self, controller, request, callback):
        info = HeartbeatInfo()
        info.need_heartbeat = self.channel.need_heartbeat
        if info.need_heartbeat:
            info.heartbeat_interval = self.channel.heartbeat_interval
        callback(info)

    def notify_heartbeat(self, controller, request, callback):
        controller.conn.clear_heartbeat_counter()
