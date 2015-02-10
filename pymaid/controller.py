__all__ = ['Controller']

from google.protobuf.service import RpcController

from pymaid.error import BaseError
from pb.pymaid_pb2 import Controller as Meta, ErrorMessage


class Controller(RpcController):

    def __init__(self):
        self.meta, self.broadcast, self.group = Meta(), False, None
        self._content = ''

    def Reset(self):
        self.meta.Clear()
        self.conn, self.broadcast, self.group = None, False, None
        self._content = ''

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

    def StartCancel(self):
        pass

    def SetFailed(self, reason):
        self.meta.is_failed = True
        if isinstance(reason, BaseError):
            message = ErrorMessage(
                error_code=reason.code, error_message=reason.message
            )
            self.content = message.SerializeToString()
        else:
            self.content = repr(reason)

    def IsCanceled(self):
        return self.meta.is_canceled

    def NotifyOnCancel(self, callback):
        pass
