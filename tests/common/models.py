from pymaid.net.channel import StreamChannel
from pymaid.net.stream import Stream
from pymaid.types import DataType


class TestStreamChannel(StreamChannel):

    # for test case only
    def connection_made(self, sock):
        self.connected_stream = super().connection_made(sock)
        return self.connected_stream


class TestStream(Stream):

    # for test case only
    def data_received(self, data: DataType):
        self.received_data = data


del StreamChannel, Stream
