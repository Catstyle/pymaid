from pymaid.error import BaseError
from pb.pymaid_pb2 import Controller, ErrorMessage


def __init__(self, *args, **kwargs):
    super(Controller, self).__init__(*args, **kwargs)
    self.__dict__['conn'] = None
    self.__dict__['broadcast'] = False
    self.__dict__['group'] = None


def Reset(self):
    self.Clear()
    self.__dict__['broadcast'] = False
    self.__dict__['group'] = None


def Failed(self):
    return self.is_failed


def ErrorText(self):
    return self.message


def StartCancel(self):
    pass


def SetFailed(self, reason):
    self.is_failed = True
    if isinstance(reason, BaseError):
        message = ErrorMessage(
            error_code=reason.code, error_message=reason.message
        )
        self.message = message.SerializeToString()
    else:
        self.message = repr(reason)


def IsCanceled(self):
    return self.is_canceled


def NotifyOnCancel(self, callback):
    pass


def property_setter(controller, name):

    def setter(self, value):
        self.__dict__[name] = value
    setattr(controller, 'set_' + name, setter)


Controller.__init__ = __init__
Controller.Reset = Reset
Controller.Failed = Failed
Controller.ErrorText = ErrorText
Controller.StartCancel = StartCancel
Controller.SetFailed = SetFailed
Controller.IsCanceled = IsCanceled
Controller.NotifyOnCancel = NotifyOnCancel

property_setter(Controller, 'conn')
property_setter(Controller, 'broadcast')
property_setter(Controller, 'group')
property_setter(Controller, 'parser_type')
property_setter(Controller, 'packet_type')
