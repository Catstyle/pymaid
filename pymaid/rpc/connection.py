from typing import TypeVar

from pymaid.net.stream import Stream


class Connection(Stream):
    '''Connection represent a communication way for client <--> server

    It holds the low level transport.
    '''

    KEEP_OPEN_ON_EOF = True

    def __init__(
        self,
        sock,
        *,
        protocol,
        handler,
        **kwargs
    ):
        super().__init__(sock, **kwargs)
        self.protocol = protocol
        self.handler = handler
        self.read_buffer = bytearray()

        # NOTE: cyclic
        handler.start(self)

    def data_received(self, data: bytes):
        '''Received data from low level transport'''
        self.read_buffer.extend(data)
        used_size, messages = self.protocol.feed_data(self.read_buffer)
        if used_size:
            self.read_buffer = self.read_buffer[used_size:]
            self.handler.feed_messages(messages)

    async def send_message(self, *args, **kwargs):
        '''Helper to send protocol message'''
        await self.write(self.protocol.encode(*args, **kwargs))

    def close(self, exc=None):
        if self.state == self.STATE.CLOSED:
            return
        self.handler.shutdown(exc)
        super().close(exc)

    def _finnal_close(self, exc=None):
        super()._finnal_close(exc)
        self.handler.close(exc)
        del self.handler
        del self.read_buffer[:]


ConnectionType = TypeVar('Connection', bound=Connection)
