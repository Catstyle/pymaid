from .pymaid_pb2 import Controller as Meta

__all__ = ['Controller']


class Controller(object):

    __slots__ = ['meta', 'conn', 'header_buf']

    def __init__(self, meta=None, conn=None, **kwargs):
        self.meta, self.conn = meta or Meta(**kwargs), conn

    def Reset(self):
        self.meta.Clear()

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
