class BaseMeta(type):

    errors = {}
    warnings = {}
    
    def __init__(cls, name, bases, attrs):
        super(BaseMeta, cls).__init__(name, bases, attrs)
        if name in ['BaseError', 'Error', 'Warning']:
            return

        if issubclass(cls, Error):
            assert cls.code not in BaseMeta.errors
            BaseMeta.errors[cls.code] = cls
        if issubclass(cls, Warning):
            assert cls.code not in BaseMeta.warnings
            BaseMeta.warnings[cls.code] = cls
        assert hasattr(cls, 'message_format')


class BaseError(Exception):

    __metaclass__ = BaseMeta

    def __init__(self, **kwargs):
        if kwargs:
            self.message = self.message_format.format(**kwargs)


class Error(BaseError):
    pass


class Warning(BaseError):
    pass
