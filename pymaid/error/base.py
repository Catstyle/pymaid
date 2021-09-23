import abc
from sys import _getframe as getframe

from orjson import loads


class BaseEx(Exception, metaclass=abc.ABCMeta):

    code = None
    message = 'BaseEx'

    def __init__(self, *args, **kwargs):
        if '_message_' in kwargs:
            message = kwargs.pop('_message_')
        else:
            message = self.message
        if args or kwargs:
            message = message.format(*args, **kwargs)
        self.message = message
        self.data = kwargs.get('data', {})

    @classmethod
    def wraps(cls, target: Exception):
        cls.register(target)
        return target


class Error(BaseEx):

    def __str__(self):
        return '[ERROR][code|{}][message|{}][data|{}]'.format(
            self.code, self.message, self.data
        )
    __repr__ = __str__

    def __bytes__(self):
        return '[ERROR][code|{}][message|{}][data|{}]'.format(
            self.code, self.message, self.data
        ).encode('utf-8')


class Warning(BaseEx):

    def __str__(self):
        return '[WARN][code|{}][message|{}][data|{}]'.format(
            self.code, self.message, self.data
        )
    __repr__ = __str__

    def __bytes__(self):
        return '[WARN][code|{}][message|{}][data|{}]'.format(
            self.code, self.message, self.data
        ).encode('utf-8')


class ErrorManager(metaclass=abc.ABCMeta):

    codes = {}
    managers = {}
    __fullname__ = ''

    def __new__(cls, *args, **kwargs):
        if cls is ErrorManager or ErrorManager in cls.__bases__:
            raise TypeError('should not initiate ErrorManager')
        return super().__new__(cls, *args, **kwargs)

    @classmethod
    def add(cls, name, ex):
        if ex.code in cls.codes:
            raise ValueError(f'duplicated exception code: {ex.code}')
        cls.codes[ex.code] = ex
        setattr(cls, name, ex)

    @classmethod
    def add_manager(cls, name, manager):
        cls.managers[manager.__name__] = manager
        setattr(cls, name, manager)

    @classmethod
    def add_error(cls, name, message, *, code=None):
        frame = getframe(1)  # get caller frame
        if cls.__fullname__:
            fullname = f'{cls.__fullname__}.{name}'
        else:
            fullname = name
        error = type(
            name, (Error, cls),
            {
                'code': code if code is not None else fullname,
                'message': message,
                '__module__': frame.f_locals.get('__name__', ''),
                '__fullname__': fullname,
            }
        )
        cls.add(name, error)
        cls.register(error)
        return error

    @classmethod
    def add_warning(cls, name, message, *, code=None):
        frame = getframe(1)  # get caller frame
        if cls.__fullname__:
            fullname = f'{cls.__fullname__}.{name}'
        else:
            fullname = name
        warning = type(
            name,
            (Warning, cls),
            {
                'code': code if code is not None else fullname,
                'message': message,
                '__module__': frame.f_locals.get('__name__', ''),
                '__fullname__': fullname,
            }
        )
        cls.add(name, warning)
        cls.register(warning)
        return warning

    @classmethod
    def get_exception(cls, code):
        try:
            return cls.codes[code]
        except KeyError:
            for manager in cls.managers.values():
                ex = manager.get_exception(code)
                if ex is not None:
                    return ex

    @classmethod
    def assemble(cls, code, message, data):
        ex = ErrorManager.get_exception(code)
        if ex is None:
            ex = ErrorManager.add_warning('Unknown_%s' % code, message)
        ex = ex()
        ex.message = message
        if data:
            ex.data = loads(data)
        return ex

    @classmethod
    def create_manager(cls, name):
        frame = getframe(1)  # get caller frame
        kwargs = dict(cls.__dict__)
        kwargs['__module__'] = frame.f_locals.get('__name__', '')
        if cls.__fullname__:
            kwargs['__fullname__'] = f'{cls.__fullname__}.{name}'
        else:
            kwargs['__fullname__'] = name
        # added BaseEx as base class
        # for use specified :ErrorManager: in except clause
        manager = type(name, (cls, BaseEx), kwargs)
        manager.codes = {}
        manager.managers = {}
        cls.add_manager(name, manager)
        return manager
