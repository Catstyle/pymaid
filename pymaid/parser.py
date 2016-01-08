__all__ = ['PBParser', 'JSONParser']

try:
    import ujson as json
except ImportError:
    import json as json
import struct
from collections import Mapping

from google.protobuf.message import Message

HEADER = '!HH'
HEADER_LENGTH = struct.calcsize(HEADER)
HEADER_STRUCT = struct.Struct(HEADER)
pack_header = HEADER_STRUCT.pack
unpack_header = HEADER_STRUCT.unpack


def keys_to_string(data):
    if not isinstance(data, Mapping):
        return data
    return {str(k): keys_to_string(v) for k, v in data.items()}


class BaseParser(object):

    @classmethod
    def pack_meta(cls, meta, content=b''):
        if isinstance(content, Message):
            content = cls.pack(content)
        else:
            content = str(content)
        meta_content = cls.pack(meta)
        return b''.join([
            pack_header(len(meta_content), len(content)), meta_content, content
        ])

    @staticmethod
    def pack(packet):
        raise NotImplementedError

    @staticmethod
    def unpack(packet_buffer, cls):
        raise NotImplementedError


class PBParser(BaseParser):

    @staticmethod
    def pack(packet):
        return packet.SerializeToString()

    @staticmethod
    def unpack(packet_buffer, cls):
        return cls.FromString(packet_buffer)


class JSONParser(BaseParser):

    @staticmethod
    def pack(packet):
        return json.dumps(
            {field.name: value for field, value in packet.ListFields()},
            ensure_ascii=False,
        ).encode('utf-8')

    @staticmethod
    def unpack(packet_buffer, cls):
        return cls(**keys_to_string(json.loads(packet_buffer)))
