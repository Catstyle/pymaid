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

    @classmethod
    def get_by_code(cls, error_code):
        if error_code in cls.errors:
            ret = cls.errors[error_code]
        elif error_code in cls.warnings[error_code]:
            ret = cls.warnings[error_code]
        else:
            assert False, 'not definded error_code'
        return ret


class BaseError(Exception):

    __metaclass__ = BaseMeta

    def __init__(self, **kwargs):
        if kwargs:
            self.message = self.message_format.format(**kwargs)
        else:
            self.message = self.message_format


class Error(BaseError):

    def __unicode__(self):
        return u'[ERROR][code|{0}][message|{1}]'.format(self.code, self.message)
    __str__ = __unicode__


class Warning(BaseError):

    def __unicode__(self):
        return u'[WARNING][code|{0}][message|{1}]'.format(self.code, self.message)
    __str__ = __unicode__
