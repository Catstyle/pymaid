__all__ = ['Controller']
from functools import partial

from google.protobuf.service import RpcController

from pymaid.parser import pack, get_unpack
from .pymaid_pb2 import Controller as Meta


class Controller(RpcController):

    __slots__  = ['meta', 'conn', 'pack', 'unpack']

    def __init__(self, meta=None, conn=None, parser_type=None, **kwargs):
        self.meta, self.conn = meta or Meta(**kwargs), conn
        if parser_type:
            self.pack = partial(pack, parser_type=parser_type)
            self.unpack = get_unpack(parser_type)
        else:
            self.pack = self.unpack = None

    def Reset(self):
        self.meta.Clear()
        self.conn = self.pack = self.unpack = None

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
