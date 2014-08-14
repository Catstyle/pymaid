from google.protobuf.service import RpcController

from pymaid.error import BaseError
from pb.pymaid_pb2 import ControllerMeta, ErrorMessage


class Controller(RpcController):

    def __init__(self):
        super(Controller, self).__init__()
        self.meta_data = ControllerMeta()
        self.conn = None
        self.wide = False
        self.group = None

    def Reset(self):
        self.meta_data.Clear()
        self.conn = None
        self.wide = False
        self.group = None

    def Failed(self):
        return self.meta_data.failed

    def ErrorText(self):
        return self.meta_data.error_text

    def StartCancel(self):
        pass

    def SetFailed(self, reason):
        assert isinstance(reason, BaseError)
        self.meta_data.failed = True
        error_message = ErrorMessage(error_code=reason.code,
                                     error_message=reason.message)
        self.meta_data.error_text = error_message.SerializeToString()

    def IsCanceled(self):
        return self.meta_data.is_canceled

    def NotifyOnCancel(self, callback):
        pass
