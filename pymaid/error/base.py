import abc
from sys import _getframe as getframe

import six
from ujson import loads


class BaseEx(Exception):

    code = None
    message = 'BaseEx'

    def __init__(self, *args, **kwargs):
        if args or kwargs:
            self.message = self.message.format(*args, **kwargs)
        self.data = kwargs.get('data', {})


class Error(BaseEx):

    if six.PY2:
        def __str__(self):
            return u'[ERROR][{}][code|{}][message|{}][data|{}]'.format(
                self.__class__.__name__, self.code, self.message, self.data
            ).encode('utf-8')
        __repr__ = __str__

        def __unicode__(self):
            return u'[ERROR][{}][code|{}][message|{}][data|{}]'.format(
                self.__class__.__name__, self.code, self.message, self.data
            )
    else:
        def __str__(self):
            return u'[ERROR][{}][code|{}][message|{}][data|{}]'.format(
                self.__class__.__name__, self.code, self.message, self.data
            )
        __repr__ = __str__

        def __bytes__(self):
            return u'[ERROR][{}][code|{}][message|{}][data|{}]'.format(
                self.__class__.__name__, self.code, self.message, self.data
            ).encode('utf-8')


class Warning(BaseEx):

    if six.PY2:
        def __str__(self):
            return u'[WARN][{}][code|{}][message|{}][data|{}]'.format(
                self.__class__.__name__, self.code, self.message, self.data
            ).encode('utf-8')
        __repr__ = __str__

        def __unicode__(self):
            return u'[WARN][{}][code|{}][message|{}][data|{}]'.format(
                self.__class__.__name__, self.code, self.message, self.data
            )
    else:
        def __str__(self):
            return u'[WARN][{}][code|{}][message|{}][data|{}]'.format(
                self.__class__.__name__, self.code, self.message, self.data
            )
        __repr__ = __str__

        def __bytes__(self):
            return u'[WARN][{}][code|{}][message|{}][data|{}]'.format(
                self.__class__.__name__, self.code, self.message, self.data
            ).encode('utf-8')


@six.add_metaclass(abc.ABCMeta)
class ErrorManager(BaseEx):

    index = 0
    codes = {}
    exceptions = {}
    managers = {}

    @classmethod
    def add(cls, name, ex):
        if ex.code in cls.codes:
            raise ValueError('duplicated exception code: %d', ex.code)
        cls.codes[ex.code] = ex
        cls.exceptions[name] = ex
        setattr(cls, name, ex)

    @classmethod
    def add_manager(cls, name, manager):
        cls.managers[manager.__name__] = manager
        setattr(cls, name, manager)

    @classmethod
    def add_error(cls, name, code, message):
        frame = getframe(1)  # get caller frame
        error = type(
            name, (Error, cls),
            {'code': cls.index + code, 'message': message,
             '__module__': frame.f_locals.get('__name__', '')}
        )
        cls.add(name, error)
        cls.register(error)
        return error

    @classmethod
    def add_warning(cls, name, code, message):
        frame = getframe(1)  # get caller frame
        warning = type(
            name, (Warning, cls),
            {'code': cls.index + code, 'message': message,
             '__module__': frame.f_locals.get('__name__', '')}
        )
        cls.add(name, warning)
        cls.register(warning)
        return warning

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
    def assemble(cls, code, message, data):
        ex = ErrorManager.get_exception(code)
        if ex is None:
            ex = ErrorManager.add_warning('Unknown_%s' % code, code, message)
        ex = ex()
        ex.message = message
        if data:
            ex.data = loads(data)
        return ex

    @classmethod
    def create_manager(cls, name, index):
        frame = getframe(1)  # get caller frame
        kwargs = dict(ErrorManager.__dict__)
        kwargs['__module__'] = frame.f_locals.get('__name__', '')
        manager = type(name, (ErrorManager,), kwargs)
        manager.index = index
        manager.codes = {}
        manager.exceptions = {}
        manager.managers = {}
        cls.add_manager(name, manager)
        return manager
