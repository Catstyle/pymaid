from struct import Struct
from typing import Optional, Sequence, Tuple, TypeVar

from google.protobuf.message import Message

from pymaid.conf import settings
from pymaid.net import DataType, Protocol

from .error import PBError
from .pymaid_pb2 import Context as Meta

st = Struct(settings.get('PM_PB_HEADER', ns='pymaid'))
header_size = st.size
pack_header = st.pack
unpack_header = st.unpack

Message = TypeVar('Message', bound=Message)


class Protocol(Protocol):

    def feed_data(self, data: DataType) -> Tuple[int, Sequence[Message]]:
        data = memoryview(data)
        messages = []

        used_size = 0
        max_packet = settings.get('MAX_PACKET_LENGTH', ns='pymaid')
        try:
            while 1:
                consumed, meta, payload = self.decode(data, max_packet)
                if not consumed:
                    break
                assert meta
                assert meta.payload_size == len(payload)
                messages.append((meta, payload))
                used_size += consumed
                data = data[consumed:]
        finally:
            data.release()

        return used_size, messages

    def encode(self, meta: Meta, message: Message) -> bytes:
        meta.payload_size = message.ByteSize()
        return (
            pack_header(meta.ByteSize())
            + meta.SerializeToString()
            + message.SerializeToString()
        )

    def decode(
        self, data: memoryview, max_packet: int
    ) -> Tuple[int, Optional[Meta], Optional[memoryview]]:
        nbytes = data.nbytes
        if nbytes < header_size:
            return 0, None, None

        needed_size = header_size
        meta_size = unpack_header(data[:needed_size])[0]
        needed_size += meta_size
        if nbytes < needed_size:
            return 0, None, None

        meta = Meta.FromString(data[header_size:needed_size])
        if meta.payload_size > max_packet:
            raise PBError.PacketTooLarge(
                data={'max': max_packet, 'size': meta.payload_size}
            )
        if header_size + meta_size + meta.payload_size > nbytes:
            return 0, None, None
        needed_size += meta.payload_size

        return needed_size, meta, data[header_size + meta_size: needed_size]
