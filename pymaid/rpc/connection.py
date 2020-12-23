from typing import Optional, TypeVar

from pymaid.core import create_task
from pymaid.net import TransportType, ProtocolType
from pymaid.utils.logger import logger_wrapper

from .types import HandlerType


@logger_wrapper
class Connection:
    '''Connection represent a communication way for client <--> server

    It holds the low level transport.
    '''

    def __init__(
        self,
        transport: TransportType,
        protocol: ProtocolType,
        handler: HandlerType,
    ):
        self.transport = transport
        self.is_closed = False
        self.protocol = protocol
        self.handler = handler

        self.buffer = bytearray()

        # cyclic
        handler.handle(self)

    def shutdown(self):
        self.transport.shutdown()

    async def join(self):
        await self.handler.join()
        await self.close()

    async def close(self, exc: Optional[Exception] = None):
        if self.is_closed:
            return
        self.is_closed = True
        self.transport.close(exc)
        # break cyclic
        self.transport = None
        await self.handler.close(exc)
        self.handler = None
        del self.buffer[:]

    def feed_data(self, data: bytes, addr=None) -> Optional[bool]:
        '''Received data from low level transport'''
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
        '''Coroutine to send data to low level transport'''
        self.transport.write(self.protocol.encode(meta, message))

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} transport={self.transport}>'


ConnectionType = TypeVar('Connection', bound=Connection)
