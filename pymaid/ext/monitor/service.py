from pymaid.rpc import Void
from pymaid.rpc.utils import implall

from .monitor_pb2 import MonitorService, Pong


@implall
class MonitorServiceImpl(MonitorService):

    async def Ping(self, request: Void, context) -> Pong:
        if not context.conn.is_closed:
            context.conn.clear_heartbeat_counter()
        return Pong()
