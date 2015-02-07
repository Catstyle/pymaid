__all__ = ['DEFAULT_PARSER', 'PBParser']

from pymaid.controller import Controller


class PBParser(object):
    '''Google Protocol Buffer Parser'''

    @staticmethod
    def parse_packet(packet_buffer):
        controller = Controller()
        controller.ParseFromString(packet_buffer)
        return controller


DEFAULT_PARSER = PBParser
