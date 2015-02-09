__all__ = [
    'DEFAULT_PARSER', 'PBParser', 'JSONParser', 'get_parser',
    'pack_packet', 'unpack_packet'
]

try:
    import ujson as json
except ImportError:
    import json as json

from pymaid.controller import Controller
from pymaid.error import ParserNotExist


class PBParser(object):
    '''Google Protocol Buffer Parser'''

    @staticmethod
    def pack_packet(packet):
        return packet.SerializeToString()

    @staticmethod
    def unpack_packet(packet_buffer):
        controller = Controller()
        controller.meta.ParseFromString(packet_buffer)
        return controller


class JSONParser(object):
    '''Google Protocol Buffer Parser'''

    @staticmethod
    def pack_packet(packet):
        return json.dumps(packet)

    @staticmethod
    def unpack_packet(packet_buffer):
        return json.loads(packet_buffer)


# packet type
REQUEST = 1
RESPONSE = 2
NOTIFICATION = 3

# parser type
PB = 1
JSON = 2
DEFAULT_PARSER = PB


PARSERS = {
    PB: PBParser,
    JSON: JSONParser
}


def get_parser(parser_type):
    if parser_type not in PARSERS:
        raise ParserNotExist(parser_type=parser_type)
    return PARSERS[parser_type]


def pack_packet(packet, parser_type):
    if parser_type not in PARSERS:
        raise ParserNotExist(parser_type=parser_type)
    return PARSERS[parser_type].pack_packet(packet)


def unpack_packet(packet_buffer, parser_type):
    if parser_type not in PARSERS:
        raise ParserNotExist(parser_type=parser_type)
    return PARSERS[parser_type].unpack_packet(packet_buffer)
