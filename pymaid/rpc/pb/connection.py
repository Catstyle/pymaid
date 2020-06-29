from typing import Optional

from pymaid.core import create_task
from pymaid.net import TransportType
from pymaid.rpc.channel import Connection
from pymaid.rpc.controller import C, InboundController, OutboundController
from pymaid.utils.logger import logger_wrapper

from .error import PBError


@logger_wrapper
class Connection(Connection):

    MAX_TRANSMISSION_ID = 2 ** 32 - 1

    def __init__(
        self,
        transport: TransportType,
        protocol,
        handler,
    ):
        super().__init__(transport)
        self.protocol = protocol
        self.handler = handler
        # cyclic
        handler.conn = self

        self.controllers = {}
        self.buffer = bytearray()

        self.inbound_transmission_id = 0

        # for server side, the id will be EVEN
        # for client size, the id will be ODD
        if transport.client_side:
            self.outbound_transmission_id = 1
        else:
            self.outbound_transmission_id = 2

    async def join(self):
        await self.handler.join()
        self.close()

    def close(self, exc=None):
        if self.is_closed:
            return
        super().close(exc)
        self.handler.close(exc)
        del self.buffer[:]
        for cntl in list(self.controllers.values()):
            cntl.close(exc)

    def feed_data(self, data: bytes) -> Optional[bool]:
        if not data:
            create_task(self.join())
            return True

        self.buffer.extend(data)
        try:
            used_size, messages = self.protocol.feed_data(self.buffer)
        except Exception as exc:
            self.close(exc)
        else:
            if used_size:
                assert messages
                self.buffer = self.buffer[used_size:]
                self.handler.feed_message(messages)

    def get_controller(self, transmission_id: int) -> C:
        return self.controllers.get(transmission_id)

    def release_controller(self, transmission_id: int):
        if transmission_id not in self.controllers:
            # already released ?
            return
        self.controllers.pop(transmission_id)

    def next_transmission_id(self) -> int:
        '''Return the next available transmission id for the controller created
        by this endpoint.

        :raises: :class:`NoAvailableTransmissionID
            <pymaid.rpc.pb.error.PBError.NoAvailableTransmissionID>`
        :returns: the next id can be initiate a Controller
        :rtype: ``int``
        '''
        transmission_id = self.outbound_transmission_id
        if transmission_id > self.MAX_TRANSMISSION_ID:
            raise PBError.NoAvailableTransmissionID(
                data={'id': transmission_id, 'max': self.MAX_TRANSMISSION_ID}
            )
        self.outbound_transmission_id += 2
        return self.outbound_transmission_id

    def new_inbound_controller(
        self,
        transmission_id: int,
        *,
        method,
        timeout: Optional[float] = None,
    ) -> C:
        # it is hard to insist the inbound_transmission_id order
        # e.g.
        # client make 3 async calls: 1, 3, 5
        # all 3 run parallelly, then orders are unspecified

        # if transmission_id < self.inbound_transmission_id:
        #     raise PBError.InvalidTransmissionID(
        #         data={
        #             'tid': transmission_id,
        #             'reason': 'reused transmission id',
        #         }
        #     )

        assert transmission_id not in self.controllers, 'reuse transmission id'
        if not self.transport.client_side and transmission_id % 2 != 1:
            raise PBError.InvalidTransmissionID(
                data={
                    'tid': transmission_id,
                    'reason': 'invalid inbound transmission id value',
                }
            )
        self.inbound_transmission_id = transmission_id

        # warning: cyclic referrence
        controller = InboundController(
            conn=self,
            transmission_id=transmission_id,
            method=method,
            timeout=timeout,
        )
        self.controllers[transmission_id] = controller
        return controller

    def new_outbound_controller(
        self,
        *,
        method,
        timeout: Optional[float] = None,
    ) -> C:
        transmission_id = self.next_transmission_id()
        # warning: cyclic referrence
        controller = OutboundController(
            conn=self,
            transmission_id=transmission_id,
            method=method,
            timeout=timeout,
        )
        self.controllers[transmission_id] = controller
        return controller

    def send_message(self, meta, message):
        self.transport.write(self.protocol.encode(meta, message))
