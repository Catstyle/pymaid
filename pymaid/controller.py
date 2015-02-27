__all__ = ['Controller']

from google.protobuf.service import RpcController

from pymaid.parser import pack_packet, pack_header
from pymaid.error import BaseError
from pymaid.pb.pymaid_pb2 import Controller as Meta, ErrorMessage


class Controller(RpcController):

    __slots__  = [
        'meta', 'conn', 'broadcast', 'group', 'parser_type', '_content'
    ]

    def __init__(self, meta_buffer=None, **kwargs):
        self.meta = meta_buffer and Meta.FromString(meta_buffer) or Meta(**kwargs)
        self.broadcast, self.group, self._content = False, None, b''

    def Reset(self):
        self.meta.Clear()
        self.conn, self.broadcast, self.group = None, False, None
        self._content = b''

    def Failed(self):
        return self.meta.is_failed

    def ErrorText(self):
        return self._content

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, value):
        self._content = value
        self.meta.content_size = len(value)

    def pack_content(self, content):
        self.content = pack_packet(content, self.parser_type)

    def pack_packet(self):
        parser_type = self.parser_type
        packet_buffer = pack_packet(self.meta, parser_type)
        return b''.join([
            pack_header(parser_type, len(packet_buffer)),
            packet_buffer,
            self._content
        ])

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
