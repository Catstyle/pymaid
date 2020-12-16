from typing import Optional

from pymaid.core import create_task
from pymaid.net import TransportType
from pymaid.rpc.channel import Connection
from pymaid.utils.logger import logger_wrapper


@logger_wrapper
class Connection(Connection):

    def __init__(
        self,
        transport: TransportType,
        protocol,
        handler,
    ):
        super().__init__(transport)
        self.protocol = protocol
        self.handler = handler

        self.buffer = bytearray()

        # cyclic
        handler.handle(self)

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

    async def send_message(self, meta, message):
        self.transport.write(self.protocol.encode(meta, message))
