__all__ = ['Controller']

from google.protobuf.service import RpcController

from pymaid.parser import pack_packet, unpack_packet, pack_header
from pymaid.error import BaseError
from pymaid.pb.pymaid_pb2 import Controller as Meta, ErrorMessage


class Controller(RpcController):

    __slots__  = [
        'meta', 'conn', 'broadcast', 'group', 'parser_type', 'content'
    ]

    def __init__(self, meta=None, parser_type=None, **kwargs):
        self.meta, self.parser_type = meta or Meta(**kwargs), parser_type
        self.broadcast, self.group, self.content = False, None, b''

    def Reset(self):
        self.meta.Clear()
        self.conn, self.broadcast, self.group = None, False, None
        self.content, self.parser_type = b'', None

    def Failed(self):
        return self.meta.is_failed

    def ErrorText(self):
        return self.content

    def pack_content(self, content):
        self.content = pack_packet(content, self.parser_type)

    def unpack_content(self, cls):
        return unpack_packet(self.content, cls, self.parser_type)

    def pack_packet(self):
        parser_type = self.parser_type
        packet_buffer = pack_packet(self.meta, parser_type)
        return b''.join([
            pack_header(parser_type, len(packet_buffer), len(self.content)),
            packet_buffer,
            self.content
        ])

    @classmethod
    def unpack_packet(cls, packet_buffer, parser_type):
        meta = unpack_packet(packet_buffer, Meta, parser_type)
        return cls(meta=meta, parser_type=parser_type)

    def StartCancel(self):
        pass

    def SetFailed(self, reason):
        self.meta.is_failed = True
        if isinstance(reason, BaseError):
            message = ErrorMessage(
                error_code=reason.code, error_message=reason.message
            )
            self.pack_content(message)
        else:
            self.content = repr(reason)

    def IsCanceled(self):
        return self.meta.is_canceled

    def NotifyOnCancel(self, callback):
        pass
