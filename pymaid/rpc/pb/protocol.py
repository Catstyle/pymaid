import struct
from typing import Optional, Sequence, Tuple, TypeVar

from google.protobuf.message import Message

from pymaid.net.protocol import DataType, Protocol

from .error import PBError
from .pymaid_pb2 import Context as Meta


Message = TypeVar('Message', bound=Message)


class Protocol(Protocol):

    HEADER_FORMAT = '!HH'
    HEADER_STRUCT = struct.Struct(HEADER_FORMAT)

    MAX_PACKET_LENGTH = 8 * 1024

    header_size = HEADER_STRUCT.size
    pack_header = HEADER_STRUCT.pack
    unpack_header = HEADER_STRUCT.unpack

    @classmethod
    def feed_data(cls, data: DataType) -> Tuple[int, Sequence[Message]]:
        data = memoryview(data)
        messages = []

        used_size = 0
        try:
            while 1:
                consumed, meta, payload = cls.decode(data)
                if not consumed:
                    break
                messages.append((meta, payload))
                used_size += consumed
                data = data[consumed:]
        finally:
            data.release()

        return used_size, messages

    @classmethod
    def encode(cls, meta: Meta, message: Message) -> bytes:
        return (
            cls.pack_header(meta.ByteSize(), message.ByteSize())
            + meta.SerializeToString()
            + message.SerializeToString()
        )

    @classmethod
    def decode(
        cls, data: DataType,
    ) -> Tuple[int, Optional[Meta], Optional[memoryview]]:
        header_size = cls.header_size
        if (data_size := len(data)) < header_size:
            return 0, None, None

        meta_size, payload_size = cls.unpack_header(data[:header_size])
        if (used_size := header_size + meta_size + payload_size) > data_size:
            return 0, None, None
        if payload_size > cls.MAX_PACKET_LENGTH:
            raise PBError.PacketTooLarge(
                data={'max': cls.MAX_PACKET_LENGTH, 'size': payload_size}
            )

        return (
            used_size,
            Meta.FromString(data[header_size:header_size + meta_size]),
            data[header_size + meta_size: used_size],
        )
