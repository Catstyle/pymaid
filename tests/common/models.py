from pymaid.net.channel import StreamChannel
from pymaid.net.stream import Stream
from pymaid.types import DataType


class _TestStreamChannel(StreamChannel):

    # for test case only
    def connection_made(self, sock):
        self.connected_stream = super().connection_made(sock)
        return self.connected_stream


class _TestStream(Stream):

    # for test case only
    def data_received(self, data: DataType):
        self.logger.debug(f'{self!r} data_received, {len(data)=}')
        self.received_data = data


del StreamChannel, Stream
