from google.protobuf.service import RpcController

from pymaid.error import BaseError
from pb.pymaid_pb2 import ControllerMeta, ErrorMessage


class Controller(RpcController):

    def __init__(self, *args, **kwargs):
        super(Controller, self).__init__(*args, **kwargs)
        self.meta_data = ControllerMeta()
        self.conn = None
        self.broadcast = False
        self.group = None

    def Reset(self):
        self.meta_data.Clear()
        self.broadcast = False
        self.group = None

    def Failed(self):
        return self.meta_data.is_failed

    def ErrorText(self):
        return self.meta_data.message

    def StartCancel(self):
        pass

    def SetFailed(self, reason):
        self.meta_data.is_failed = True
        if isinstance(reason, BaseError):
            message = ErrorMessage(
                error_code=reason.code, error_message=reason.message
            )
            self.meta_data.message = message.SerializeToString()
        else:
            self.meta_data.message = repr(reason)

    def IsCanceled(self):
        return self.meta_data.is_canceled

    def NotifyOnCancel(self, callback):
        pass
