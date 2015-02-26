__all__ = [
    'DEFAULT_PARSER', 'PBParser', 'JSONParser', 'get_parser',
    'pack_packet', 'unpack_packet'
]

import struct
import six
try:
    import ujson as json
except ImportError:
    import json as json

import pymaid
from pymaid.error import ParserNotExist


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
    def unpack_packet(packet_buffer):
        raise NotImplementedError


class PBParser(Parser):
    '''Google Protocol Buffer Parser'''

    parser_type = 1

    @staticmethod
    def pack_packet(meta):
        return meta.SerializeToString()

    @staticmethod
    def unpack_packet(packet_buffer):
        controller = pymaid.Controller()
        controller.meta.ParseFromString(packet_buffer)
        controller.parser_type = PBParser.parser_type
        return controller


class JSONParser(Parser):
    '''JSON style parser'''

    parser_type = 2

    @staticmethod
    def pack_packet(meta):
        return bytes(
            json.dumps({field.name: value for field, value in meta.ListFields()}),
            'utf-8'
        )

    @staticmethod
    def unpack_packet(packet_buffer):
        controller = pymaid.Controller(**json.loads(packet_buffer))
        controller.parser_type = JSONParser.parser_type
        return controller


# packet type
REQUEST = 1
RESPONSE = 2
NOTIFICATION = 3

DEFAULT_PARSER = PBParser.parser_type
DEFAULT_PARSER = JSONParser.parser_type


HEADER = '!BH'
HEADER_LENGTH = struct.calcsize(HEADER)
HEADER_STRUCT = struct.Struct(HEADER)
pack_header = HEADER_STRUCT.pack
unpack_header = HEADER_STRUCT.unpack


def get_parser(parser_type):
    if parser_type not in parsers:
        raise ParserNotExist(parser_type=parser_type)
    return parsers[parser_type]


def pack_packet(packet, parser_type):
    if parser_type not in parsers:
        raise ParserNotExist(parser_type=parser_type)
    return parsers[parser_type].pack_packet(packet)


def unpack_packet(packet_buffer, parser_type):
    if parser_type not in parsers:
        raise ParserNotExist(parser_type=parser_type)
    return parsers[parser_type].unpack_packet(packet_buffer)
