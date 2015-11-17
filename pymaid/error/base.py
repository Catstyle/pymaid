import six


class ErrorMeta(type):

    errors = {}
    warnings = {}

    def __init__(cls, name, bases, attrs):
        super(ErrorMeta, cls).__init__(name, bases, attrs)
        if name in ['BaseEx', 'Error', 'Warning']:
            return

        if issubclass(cls, Error):
            assert cls.code not in ErrorMeta.errors
            ErrorMeta.errors[cls.code] = cls
        if issubclass(cls, Warning):
            assert cls.code not in ErrorMeta.warnings
            ErrorMeta.warnings[cls.code] = cls
        assert hasattr(cls, 'message_format')


@six.add_metaclass(ErrorMeta)
class BaseEx(Exception):

    def __init__(self, *args, **kwargs):
        if args or kwargs:
            self.message = self.message_format.format(*args, **kwargs)
        else:
            self.message = self.message_format


class Error(BaseEx):

    def __unicode__(self):
        return u'[ERROR][code|{0}][message|{1}]'.format(self.code, self.message)
    __repr__ = __str__ = __unicode__


class Warning(BaseEx):

    def __unicode__(self):
        return u'[WARNING][code|{0}][message|{1}]'.format(self.code, self.message)
    __repr__ = __str__ = __unicode__


class Builder(object):

    def __init__(self, index):
        self.index = index

    def build_error(self, name, code, message_format):
        setattr(
            self, name,
            type(name, (Error,),
                 {'code': self.index+code, 'message_format': message_format})
        )

    def build_warning(self, name, code, message_format):
        setattr(
            self, name,
            type(name, (Warning,),
                 {'code': self.index+code, 'message_format': message_format})
        )


def get_ex_by_code(code):
    if code in ErrorMeta.errors:
        return ErrorMeta.errors[code]
    elif code in ErrorMeta.warnings:
        return ErrorMeta.warnings[code]
    else:
        assert False, 'undefinded code'
