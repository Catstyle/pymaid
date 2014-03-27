from google.protobuf.service import RpcController
from pb.controller_pb2 import ControllerMeta


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
        self.meta_data.failed = True
        self.meta_data.error_text = reason

    def IsCanceled(self):
        return self.meta_data.is_canceled

    def NotifyOnCancel(self, callback):
        pass
