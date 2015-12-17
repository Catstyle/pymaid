__all__ = [
    'DEFAULT_PARSER', 'pb_type', 'json_type', 'get_pack', 'get_unpack', 'pack'
]

try:
    import ujson as json
except ImportError:
    import json as json
import struct
from collections import Mapping

from google.protobuf.message import Message

from .error import RpcError

HEADER = '!BHH'
HEADER_LENGTH = struct.calcsize(HEADER)
HEADER_STRUCT = struct.Struct(HEADER)
pack_header = HEADER_STRUCT.pack
unpack_header = HEADER_STRUCT.unpack


def pack_pb_packet(packet):
    return packet.SerializeToString()


def unpack_pb_packet(packet_buffer, cls):
    return cls.FromString(packet_buffer)


def pack_json_packet(packet):
    return json.dumps(
        {field.name: value for field, value in packet.ListFields()},
        ensure_ascii=False,
    ).encode('utf-8')


def unpack_json_packet(packet_buffer, cls):
    return cls(**keys_to_string(json.loads(packet_buffer)))


packs, unpacks = {}, {}
ParserNotExist = RpcError.ParserNotExist
pb_type = 1
json_type = 2
DEFAULT_PARSER = pb_type
packs[pb_type] = pack_pb_packet
unpacks[pb_type] = unpack_pb_packet
packs[json_type] = pack_json_packet
unpacks[json_type] = unpack_json_packet


def get_pack(parser_type):
    if parser_type not in packs:
        raise ParserNotExist(parser_type=parser_type)
    return packs[parser_type]


def get_unpack(parser_type):
    if parser_type not in unpacks:
        raise ParserNotExist(parser_type=parser_type)
    return unpacks[parser_type]


def keys_to_string(data):
    if not isinstance(data, Mapping):
        return data
    return {str(k): keys_to_string(v) for k, v in data.items()}


def pack(meta, content=b'', parser_type=DEFAULT_PARSER):
    pack_function = get_pack(parser_type)
    if isinstance(content, Message):
        content = pack_function(content)
    else:
        content = str(content)
    meta_content = pack_function(meta)
    return b''.join([
        pack_header(parser_type, len(meta_content), len(content)),
        meta_content, content
    ])
