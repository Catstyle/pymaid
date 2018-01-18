import six
import abc
from sys import _getframe as getframe


class BaseEx(Exception):

    message = 'BaseEx'

    def __init__(self, *args, **kwargs):
        if args or kwargs:
            self.message = self.message.format(*args, **kwargs)


class Error(BaseEx):

    def __str__(self):
        return u'[ERROR][{}][code|{}][message|{}]'.format(
            self.__class__.__name__, self.code, self.message
        ).encode('utf-8')
    __repr__ = __str__

    def __unicode__(self):
        return u'[ERROR][{}][code|{}][message|{}]'.format(
            self.__class__.__name__, self.code, self.message
        )


class Warning(BaseEx):

    def __str__(self):
        return u'[WARN][{}][code|{}][message|{}]'.format(
            self.__class__.__name__, self.code, self.message
        ).encode('utf-8')
    __repr__ = __str__

    def __unicode__(self):
        return u'[WARN][{}][code|{}][message|{}]'.format(
            self.__class__.__name__, self.code, self.message
        )


@six.add_metaclass(abc.ABCMeta)
class ErrorManager(object):

    index = 0
    codes = {}
    exceptions = {}
    managers = {}

    @classmethod
    def add(cls, name, ex):
        setattr(cls, name, ex)
        if issubclass(ex, BaseEx):
            assert ex.code not in cls.codes, (ex.code, cls.codes)
            cls.codes[ex.code] = ex
            cls.exceptions[name] = ex
        elif issubclass(ex, ErrorManager):
            cls.managers[ex.__name__] = ex

    @classmethod
    def add_error(cls, name, code, message):
        frame = getframe(1)  # get caller frame
        error = type(
            name, (Error,),
            {'code': cls.index + code, 'message': message,
             '__module__': frame.f_locals.get('__name__', '')}
        )
        cls.register(error)
        cls.add(name, error)
        return error
    # compability
    build_error = add_error

    @classmethod
    def add_warning(cls, name, code, message):
        frame = getframe(1)  # get caller frame
        warning = type(
            name, (Warning,),
            {'code': cls.index + code, 'message': message,
             '__module__': frame.f_locals.get('__name__', '')}
        )
        cls.register(warning)
        cls.add(name, warning)
        return warning
    # compability
    build_warning = add_warning

    @classmethod
    def get_exception(cls, code):
        ex = None
        if code in cls.codes:
            ex = cls.codes[code]
        else:
            for manager in cls.managers.values():
                ex = manager.get_exception(code)
                if ex is not None:
                    return ex
        return ex

    @classmethod
    def create_manager(cls, name, index):
        frame = getframe(1)  # get caller frame
        kwargs = dict(ErrorManager.__dict__)
        kwargs['__module__'] = frame.f_locals.get('__name__', '')
        manager = type(name, (ErrorManager,), kwargs)
        manager = six.add_metaclass(abc.ABCMeta)(manager)
        manager.index = index
        manager.codes = {}
        manager.exceptions = {}
        manager.managers = {}
        cls.add(name, manager)
        return manager
