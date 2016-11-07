import logging
import logging.config

from time import time
from functools import wraps
from types import MethodType

from google.protobuf.service import Service

from pymaid.error import Warning

__all__ = [
    'create_project_logger', 'logger_wrapper', 'trace_service', 'trace_method'
]

basic_logging = {
    'version': 1,
    'formatters': {
        'standard': {
            'format': ('[%(asctime)s.%(msecs).03d] [%(levelname)s] '
                       '[pid|%(process)d] [%(name)s:%(lineno)d] %(message)s'),
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
levelnames = logging._levelNames

root_logger = logging.getLogger('root')
root_logger.wrappers = []
pymaid_logger = logging.getLogger('pymaid')
pymaid_logger.wrappers = []
project_logger = None


def create_project_logger(name):
    global project_logger
    global pymaid_logger
    assert not project_logger
    project_logger = logging.getLogger(name)
    for cls in pymaid_logger.wrappers + root_logger.wrappers:
        cls.logger = project_logger.getChild(cls.__name__)
    pymaid_logger = project_logger
    return project_logger


def pymaid_logger_wrapper(cls):
    cls.logger = pymaid_logger.getChild(cls.__name__)
    pymaid_logger.wrappers.append(cls)
    return cls


def logger_wrapper(cls):
    cls.logger = get_logger(cls.__name__)
    if cls.logger.parent is root_logger:
        root_logger.wrappers.append(cls)
    return cls


def get_logger(name):
    if project_logger:
        logger = project_logger.getChild(name)
    else:
        logger = root_logger.getChild(name)
    return logger


def update_record(record, level, msg, *args):
    record.levelno = level
    record.levelname = levelnames[level]
    record.msg = msg
    record.args = args
    ct = time()
    record.created = ct
    record.msecs = (ct - int(ct)) * 1000


def trace_service(level=logging.INFO, label=None):
    def wrapper(cls):
        assert level in levelnames, level
        for method in cls.DESCRIPTOR.methods:
            name = method.name
            setattr(cls, name, trace_method(level, label)(getattr(cls, name)))
        return cls
    if isinstance(level, str):
        level = levelnames[level]
        return wrapper
    elif isinstance(level, int):
        return wrapper
    else:
        assert issubclass(level, Service), level
        cls, level, label = level, 'INFO', None
        return wrapper(cls)


def trace_method(level=logging.INFO, label=None):
    def wrapper(func):
        assert level in levelnames, level
        co = func.func_code
        full_name = co.co_name
        if isinstance(func, MethodType):
            full_name = '%s.%s' % (func.im_class.DESCRIPTOR.name, full_name)

        # name, level, fn, lno, msg, args, exc_info, func
        record = logging.LogRecord(
            '', level, co.co_filename, co.co_firstlineno, '', (), None,
            full_name
        )
        invalid_label = 'invalid label %s' % label

        @wraps(func)
        def _(self, controller, request, done):
            assert isinstance(self, Service)

            if not label:
                pk = '[conn|%d]' % controller.conn.connid
            else:
                pk = '[conn|%d][label|%s]' % (
                    controller.conn.connid,
                    getattr(controller.conn, label, invalid_label)
                )
            req = repr(str(request))
            record.name = self.logger.name
            update_record(
                record, level, '%s [Enter|%s] [req|%s]', pk, full_name, req
            )
            self.logger.handle(record)

            def done_wrapper(resp=None, **kwargs):
                update_record(
                    record, level, '%s [Leave|%s] [resp|%s]', pk, full_name,
                    kwargs or repr(str(resp))
                )
                self.logger.handle(record)
                done(resp, **kwargs)
            try:
                return func(self, controller, request, done_wrapper)
            except BaseException as ex:
                if isinstance(ex, Warning):
                    update_record(
                        record, logging.WARN,
                        '%s [Leave|%s][req|%s] [warning|%s]',
                        pk, full_name, req, ex
                    )
                    self.logger.handle(record)
                else:
                    update_record(
                        record, logging.ERROR,
                        '%s [Leave|%s][req|%s] [exception|%s]',
                        pk, full_name, req, ex
                    )
                    self.logger.handle(record)
                raise
        return _
    if isinstance(level, str):
        level = levelnames[level]
        return wrapper
    elif isinstance(level, int):
        return wrapper
    else:
        assert callable(level), level
        func, level, pk = level, logging.INFO, 'connid'  # noqa
        return wrapper(func)
