from typing import TypeVar

from pymaid.net.transport import Transport


class Connection:
    '''Connection represent a communication way for client <--> server

    It holds the low level transport.
    '''

    KEEP_OPEN_ON_EOF = True

    def __new__(cls, *args, **kwargs):
        if not issubclass(cls, Transport):
            raise TypeError(
                'Connection need to pipe up with `Transport`, '
                'e.g. "Transport | Connection"'
            )
        return super().__new__(cls)

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
        self.__read_buffer = bytearray()

        # NOTE: cyclic
        handler.start(self)

    def data_received(self, data: bytes):
        '''Received data from low level transport'''
        self.__read_buffer.extend(data)
        used_size, messages = self.protocol.feed_data(self.__read_buffer)
        if used_size:
            self.__read_buffer = self.__read_buffer[used_size:]
            self.handler.feed_messages(messages)

    def eof_received(self):
        self.handler.shutdown('eof_received')
        return super().eof_received()

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
        del self.__read_buffer[:]


ConnectionType = TypeVar('Connection', bound=Connection)
