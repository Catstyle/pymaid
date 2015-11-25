__all__ = ['Controller']

from google.protobuf.service import RpcController

from .pymaid_pb2 import Controller as Meta


class Controller(RpcController):

    __slots__  = ['meta', 'conn', 'parser_type', 'content']

    def __init__(self, meta=None, parser_type=None, **kwargs):
        self.meta, self.parser_type = meta or Meta(**kwargs), parser_type
        self.content = b''

    def Reset(self):
        self.meta.Clear()
        self.conn, self.content, self.parser_type = None, b'', None

    def Failed(self):
        return self.meta.is_failed

    def ErrorText(self):
        return self.content

    def StartCancel(self):
        pass

    def SetFailed(self, reason=None):
        self.meta.is_failed = True

    def IsCanceled(self):
        return self.meta.is_canceled

    def NotifyOnCancel(self, callback):
        pass
