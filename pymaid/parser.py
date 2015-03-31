__all__ = [
    'DEFAULT_PARSER', 'PBParser', 'JSONParser', 'get_parser',
    'pack_packet', 'unpack_packet'
]

import struct
from collections import Mapping
import six
try:
    import ujson as json
except ImportError:
    import json as json
from pymaid.error import ParserNotExist


# packet type
REQUEST = 1
RESPONSE = 2
NOTIFICATION = 3

HEADER = '!BHH'
HEADER_LENGTH = struct.calcsize(HEADER)
HEADER_STRUCT = struct.Struct(HEADER)
pack_header = HEADER_STRUCT.pack
unpack_header = HEADER_STRUCT.unpack

parsers = {}


class ParserMeta(type):

    def __init__(cls, name, bases, attrs):
        super(ParserMeta, cls).__init__(name, bases, attrs)
        if 'parser_type' not in attrs:
            raise AttributeError('%s has not set `parser_type` attribute')
        parser_type = attrs['parser_type']
        assert parser_type not in parsers
        parsers[parser_type] = cls


@six.add_metaclass(ParserMeta)
class Parser(object):

    parser_type = None

    @staticmethod
    def pack_packet(packet):
        raise NotImplementedError

    @staticmethod
    def unpack_packet(packet_buffer, cls):
        raise NotImplementedError


class PBParser(Parser):
    '''Google Protocol Buffer Parser'''

    parser_type = 1

    @staticmethod
    def pack_packet(packet):
        return packet.SerializeToString()

    @staticmethod
    def unpack_packet(packet_buffer, cls):
        return cls.FromString(packet_buffer)


class JSONParser(Parser):
    '''JSON style parser'''

    parser_type = 2

    @staticmethod
    def pack_packet(packet):
        return json.dumps(
            {field.name: value for field, value in packet.ListFields()},
            ensure_ascii=False,
        ).encode('utf-8')

    @staticmethod
    def unpack_packet(packet_buffer, cls):
        return cls(**keys_to_string(json.loads(packet_buffer)))


DEFAULT_PARSER = PBParser.parser_type


def get_parser(parser_type):
    if parser_type not in parsers:
        raise ParserNotExist(parser_type=parser_type)
    return parsers[parser_type]


def pack_packet(packet, parser_type):
    if parser_type not in parsers:
        raise ParserNotExist(parser_type=parser_type)
    return parsers[parser_type].pack_packet(packet)


def unpack_packet(packet_buffer, cls, parser_type):
    if parser_type not in parsers:
        raise ParserNotExist(parser_type=parser_type)
    return parsers[parser_type].unpack_packet(packet_buffer, cls)


def keys_to_string(data):
    if not isinstance(data, Mapping):
        return data
    return {str(k): keys_to_string(v) for k, v in data.items()}
