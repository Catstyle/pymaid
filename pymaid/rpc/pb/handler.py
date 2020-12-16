from orjson import dumps

from pymaid.rpc.handler import Handler, SerialHandler, ParallelHandler
from pymaid.utils.logger import logger_wrapper

from .context import PBInboundContext, PBOutboundContext
from .error import PBError
from .pymaid_pb2 import Context as Meta, ErrorMessage


@logger_wrapper
class PBHandler(Handler):

    InboundContext = PBInboundContext
    OutboundContext = PBOutboundContext

    def feed_message(self, messages):
        # self.logger.debug(f'{self} feed {len(pending_tasks)=}')
        Request = Meta.PacketType.REQUEST
        Response = Meta.PacketType.RESPONSE
        get_route = self.router.get_route
        for message in messages:
            # check exist context here for a shortcut
            # because just feed message into context won't block,
            # and it makes serial streaming posible
            meta, payload = message
            if meta.transmission_id in self.contexts:
                self.contexts[meta.transmission_id].feed_message(meta, payload)
                continue

            if meta.packet_type not in {Request, Response}:
                task = self.handle_error(
                    meta,
                    PBError.InvalidPacketType(
                        data={'packet_type': meta.packet_type}
                    )
                )
            elif meta.packet_type == Request:
                name = meta.service_method
                if (rpc := get_route(name)) is None:
                    task = self.handle_error(
                        meta, PBError.RPCNotFound(data={'name': name})
                    )
                else:
                    context = self.new_inbound_context(
                        meta.transmission_id, method=rpc, timeout=self.timeout
                    )
                    context.feed_message(meta, payload)
                    task = context.run()
            elif meta.packet_type == Response:
                # invalid transmission_id, do nothing
                self.logger.warning(
                    f'{self.conn} received invalid response, '
                    f'{meta.transmission_id=}'
                )
                continue
            self.pending_tasks.append(task)
            self.new_task_received.set()

    async def handle_error(self, meta, error):
        meta.is_failed = True
        meta.packet_type = Meta.PacketType.RESPONSE
        packet = ErrorMessage(code=error.code, message=error.message)
        if error.data:
            packet.data = dumps(error.data)
        await self.conn.send_message(meta, packet)


@logger_wrapper
class PBSerialHandler(PBHandler, SerialHandler):
    pass


@logger_wrapper
class PBParallelHandler(PBHandler, ParallelHandler):
    pass
