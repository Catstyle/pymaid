import six
import abc
from sys import _getframe as getframe


_cached_classes = {}


class ErrorMeta(type):

    def __init__(cls, name, bases, attrs):
        super(ErrorMeta, cls).__init__(name, bases, attrs)
        if name in ['BaseEx', 'Error', 'Warning']:
            return

        assert cls.code not in _cached_classes, (cls.code, _cached_classes)
        _cached_classes[cls.code] = cls
        assert hasattr(cls, 'message')


@six.add_metaclass(ErrorMeta)
class BaseEx(Exception):

    def __init__(self, *args, **kwargs):
        if args or kwargs:
            self.message = self.message.format(*args, **kwargs)


class Error(BaseEx):

    def __unicode__(self):
        return u'[ERROR][{}][code|{}][message|{}]'.format(
            self.__class__.__name__, self.code, self.message
        )
    __repr__ = __str__ = __unicode__


class Warning(BaseEx):

    def __unicode__(self):
        return u'[WARN][{}][code|{}][message|{}]'.format(
            self.__class__.__name__, self.code, self.message
        )
    __repr__ = __str__ = __unicode__


class Builder(object):

    index = 0

    @classmethod
    def build_error(cls, name, code, message):
        frame = getframe(1)  # get caller frame
        error = type(
            name, (Error,),
            {'code': cls.index + code, 'message': message,
             '__module__': frame.f_locals.get('__name__', '')}
        )
        setattr(cls, name, error)
        cls.register(error)

    @classmethod
    def build_warning(cls, name, code, message):
        frame = getframe(1)  # get caller frame
        warning = type(
            name, (Warning,),
            {'code': cls.index + code, 'message': message,
             '__module__': frame.f_locals.get('__name__', '')}
        )
        setattr(cls, name, warning)
        cls.register(warning)


def get_exception(code, message):
    if code in _cached_classes:
        cls = _cached_classes[code]
    else:
        cls = type(
            'Unknown%s' % code, (Warning,), {'code': code, 'message': message}
        )
        _cached_classes[code] = cls
    ins = cls()
    ins.message = message
    return ins


def create_manager(name, index):
    frame = getframe(1)  # get caller frame
    kwargs = dict(Builder.__dict__)
    kwargs['__module__'] = frame.f_locals.get('__name__', '')
    manager = type(name, (Builder,), kwargs)
    manager = six.add_metaclass(abc.ABCMeta)(manager)
    manager.index = index
    return manager
