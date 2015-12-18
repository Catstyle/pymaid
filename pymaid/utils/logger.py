__all__ = [
    'configure_project_logger', 'pymaid_logger_wrapper', 'logger_wrapper',
    'trace_service', 'trace_method'
]
import logging
import logging.config
from functools import wraps

from google.protobuf.service import Service

basic_logging = {
    'version': 1,
    'formatters': {
        'standard': {
            'format': ('[%(asctime)s.%(msecs).03d] [pid|%(process)d] '
                       '[%(name)s:%(lineno)d] [%(levelname)s] %(message)s'),
            'datefmt': '%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'loggers': {
        'root': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'pymaid': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
logging.config.dictConfig(basic_logging)

root_logger = logging.getLogger('root')
pymaid_logger = logging.getLogger('pymaid')
project_logger = None


def configure_project_logger(name):
    global project_logger
    assert not project_logger
    project_logger = logging.getLogger(name)
    return project_logger


def pymaid_logger_wrapper(cls):
    cls.logger = pymaid_logger.getChild(cls.__name__)
    return cls


def logger_wrapper(cls):
    cls.logger = get_logger(cls.__name__)
    return cls


def get_logger(name):
    if project_logger:
        logger = project_logger.getChild(name)
    else:
        logger = root_logger.getChild(name)
    return logger


def trace_service(level='INFO'):
    def wrapper(cls):
        assert level.upper() in logging._levelNames, level
        for method in cls.DESCRIPTOR.methods:
            name = method.name
            setattr(cls, name, trace_method(level)(getattr(cls, name)))
        return cls
    if isinstance(level, str):
        return wrapper
    else:
        assert issubclass(level, Service), level
        cls, level = level, 'INFO'
        return wrapper(cls)


def trace_method(level='INFO'):
    def wrapper(func):
        assert level.upper() in logging._levelNames, level
        full_name = '%s.%s' % (func.im_class.DESCRIPTOR.name, func.__name__)
        log = getattr(func.im_class.logger, level.lower())
        @wraps(func)
        def _(self, controller, request, done):
            assert isinstance(self, Service)
            fields = {
                field.name: getattr(request, field.name)
                for field in request.DESCRIPTOR.fields
            }

            if hasattr(controller.conn, 'player'):
                pk = '[player|%s]' % controller.conn.player
            else:
                pk = '[conn|%d]' % controller.conn.connid
            log('%s [Enter|%s] [request|%s]', pk, full_name, fields)
            def done_wrapper(resp=None, **kwargs):
                log('%s [Leave|%s] [resp|%s]', pk, full_name, kwargs or resp)
                done(resp, **kwargs)
            try:
                return func(self, controller, request, done_wrapper)
            except BaseException as ex:
                log('%s [Leave|%s] [exception|%s]', pk, full_name, ex)
                raise
        return _
    if isinstance(level, str):
        return wrapper
    else:
        assert callable(level), level
        func, level = level, 'INFO'
        return wrapper(func)
