import six
import abc


class ErrorMeta(type):

    classes = {}

    def __init__(cls, name, bases, attrs):
        super(ErrorMeta, cls).__init__(name, bases, attrs)
        if name in ['BaseEx', 'Error', 'Warning']:
            return

        assert cls.code not in ErrorMeta.classes, (cls.code, ErrorMeta.classes)
        ErrorMeta.classes[cls.code] = cls
        assert hasattr(cls, 'message')


@six.add_metaclass(ErrorMeta)
class BaseEx(Exception):

    def __init__(self, *args, **kwargs):
        if args or kwargs:
            self.message = self.message.format(*args, **kwargs)


class Error(BaseEx):

    def __unicode__(self):
        return u'[ERROR][code|{}][message|{}]'.format(self.code, self.message)
    __repr__ = __str__ = __unicode__


class Warning(BaseEx):

    def __unicode__(self):
        return u'[WARN][code|{}][message|{}]'.format(self.code, self.message)
    __repr__ = __str__ = __unicode__


class Builder(object):

    index = 0

    @classmethod
    def build_error(cls, name, code, message):
        error = type(
            name, (Error,), {'code': cls.index + code, 'message': message}
        )
        setattr(cls, name, error)
        cls.register(error)

    @classmethod
    def build_warning(cls, name, code, message):
        warning = type(
            name, (Warning,), {'code': cls.index + code, 'message': message}
        )
        setattr(cls, name, warning)
        cls.register(warning)


def get_exception(code, message):
    if code in ErrorMeta.classes:
        cls = ErrorMeta.classes[code]
    else:
        cls = type(
            'RemoteEx%s' % code, (Warning,), {'code': code, 'message': message}
        )
        ErrorMeta.classes[code] = cls
    ins = cls()
    ins.message = message
    return ins


def create_manager(name, index):
    manager = type(name, (Builder,), dict(Builder.__dict__))
    manager = six.add_metaclass(abc.ABCMeta)(manager)
    manager.index = index
    return manager
