from pymaid.rpc.pb import implall

from .monitor_pb2 import MonitorService, Pong


@implall
class MonitorServiceImpl(MonitorService):

    async def Ping(self, context) -> Pong:
        if not context.conn.is_closed:
            context.conn.clear_heartbeat_counter()
        await context.send_message(Pong())
