from typing import Optional

from pymaid.core import create_task
from pymaid.net import TransportType
from pymaid.rpc.channel import Connection
from pymaid.rpc.context import C, InboundContext, OutboundContext
from pymaid.rpc.method import Method, MethodStub
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

        self.contexts = {}
        self.buffer = bytearray()

        self.inbound_transmission_id = 0

        # for initiative side, the id will be EVEN
        # for passive side, the id will be ODD
        if transport.initiative:
            self.outbound_transmission_id = 1
        else:
            self.outbound_transmission_id = 2

    async def join(self):
        await self.handler.join()
        await self.close()

    async def close(self, exc=None):
        if self.is_closed:
            return
        # base close is function
        super().close(exc)
        await self.handler.close(exc)
        self.handler = None
        del self.buffer[:]
        for ctx in list(self.contexts.values()):
            await ctx.close(exc)

    def feed_data(self, data: bytes) -> Optional[bool]:
        if not data:
            create_task(self.join())
            # return True to close low level transport
            return True

        self.buffer.extend(data)
        try:
            used_size, messages = self.protocol.feed_data(self.buffer)
        except Exception as exc:
            create_task(self.close(exc))
        else:
            if used_size:
                assert messages
                self.buffer = self.buffer[used_size:]
                self.handler.feed_message(messages)

    def get_context(self, transmission_id: int) -> C:
        return self.contexts.get(transmission_id)

    def release_context(self, transmission_id: int):
        if transmission_id not in self.contexts:
            # already released ?
            return
        self.contexts.pop(transmission_id)

    def next_transmission_id(self) -> int:
        '''Return the next available transmission id for the context created
        by this endpoint.

        :raises: :class:`NoAvailableTransmissionID
            <pymaid.rpc.pb.error.PBError.NoAvailableTransmissionID>`
        :returns: the next id can be initiate a Context
        :rtype: ``int``
        '''
        transmission_id = self.outbound_transmission_id
        if transmission_id > self.MAX_TRANSMISSION_ID:
            raise PBError.NoAvailableTransmissionID(
                data={'id': transmission_id, 'max': self.MAX_TRANSMISSION_ID}
            )
        self.outbound_transmission_id += 2
        return transmission_id

    def new_inbound_context(
        self,
        transmission_id: int,
        *,
        method: Method,
        timeout: Optional[float] = None,
    ) -> C:
        # it is hard to insist the inbound_transmission_id order
        # e.g.
        # client make 3 async calls: 1, 3, 5
        # all 3 run parallelly, then the orders are unspecified

        # if transmission_id < self.inbound_transmission_id:
        #     raise PBError.InvalidTransmissionID(
        #         data={
        #             'tid': transmission_id,
        #             'reason': 'reused transmission id',
        #         }
        #     )

        transmission_id = transmission_id
        assert transmission_id not in self.contexts, 'reused transmission id'
        if not self.transport.initiative and transmission_id % 2 != 1:
            raise PBError.InvalidTransmissionID(
                data={
                    'tid': transmission_id,
                    'reason': 'invalid inbound transmission id value',
                }
            )
        # self.inbound_transmission_id = transmission_id

        # warning: cyclic referrence
        context = InboundContext(
            conn=self,
            transmission_id=transmission_id,
            method=method,
            timeout=timeout,
        )
        self.contexts[transmission_id] = context
        return context

    def new_outbound_context(
        self,
        *,
        method: MethodStub,
        timeout: Optional[float] = None,
    ) -> C:
        transmission_id = self.next_transmission_id()
        # warning: cyclic referrence
        context = OutboundContext(
            conn=self,
            transmission_id=transmission_id,
            method=method,
            timeout=timeout,
        )
        self.contexts[transmission_id] = context
        return context

    async def send_message(self, meta, message):
        self.transport.write(self.protocol.encode(meta, message))
