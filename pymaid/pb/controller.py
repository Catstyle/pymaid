__all__ = ['Controller']

from google.protobuf.service import RpcController

from .pymaid_pb2 import Controller as Meta


class Controller(RpcController):

    __slots__  = ['meta', 'conn', 'parser_type']

    def __init__(self, meta=None, conn=None, parser_type=None, **kwargs):
        self.meta, self.conn = meta or Meta(**kwargs), conn
        self.parser_type = parser_type

    def Reset(self):
        self.meta.Clear()
        self.conn, self.parser_type = None, None

    def Failed(self):
        return self.meta.is_failed

    def ErrorText(self):
        pass

    def StartCancel(self):
        pass

    def SetFailed(self, reason=None):
        self.meta.is_failed = True

    def IsCanceled(self):
        return self.meta.is_canceled

    def NotifyOnCancel(self, callback):
        pass
