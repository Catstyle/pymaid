import logging
import logging.config
from logging import LogRecord

from collections import Mapping
from functools import wraps
from sys import _getframe as getframe
from time import time
from types import MethodType
import warnings
import sys

from google.protobuf.service import Service

from pymaid.error import Warning

__all__ = [
    'create_project_logger', 'logger_wrapper', 'trace_service', 'trace_method',
    'trace_stub'
]

if sys.version_info.major >= 3:
    logging_levels = logging._levelToName
    logging_names = logging._nameToLevel
else:
    logging_names = logging_levels = logging._levelNames

root_logger = logging.getLogger('root')
root_logger.wrappers = []
pymaid_logger = logging.getLogger('pymaid')
pymaid_logger.wrappers = []
project_logger = None


def configure_logging(settings):
    """Setup logging from PYMAID_LOGGING and LOGGING settings."""
    import logging
    import logging.config
    try:
        # Route warnings through python logging
        logging.captureWarnings(True)
        # Allow DeprecationWarnings through the warnings filters
        warnings.simplefilter("default", DeprecationWarning)
    except AttributeError:
        # No captureWarnings on Python 2.6
        # DeprecationWarnings are on anyway
        pass

    if not hasattr(settings, 'PYMAID_LOGGING'):
        settings.PYMAID_LOGGING = {}
    if hasattr(settings, 'LOGGING'):
        for key, value in settings.LOGGING.items():
            if not isinstance(value, Mapping):
                settings.PYMAID_LOGGING[key] = value
            else:
                settings.PYMAID_LOGGING[key].update(value)
    logging.config.dictConfig(settings.PYMAID_LOGGING)


def create_project_logger(name):
    global project_logger
    assert not project_logger
    project_logger = logging.getLogger(name)
    for cls in root_logger.wrappers:
        cls.logger = project_logger.getChild(cls.__name__)
    return project_logger


def pymaid_logger_wrapper(name=''):

    def _(cls):
        cls.logger = pymaid_logger.getChild(name)
        pymaid_logger.wrappers.append(cls)
        return cls

    if isinstance(name, type):
        cls, name = name, name.__name__
        return _(cls)
    else:
        return _


def logger_wrapper(name=''):

    def _(cls):
        cls.logger = get_logger(name)
        if cls.logger.parent is root_logger:
            root_logger.wrappers.append(cls)
        return cls

    if isinstance(name, type):
        cls, name = name, name.__name__
        return _(cls)
    else:
        return _


def get_logger(name):
    if project_logger:
        logger = project_logger.getChild(name)
    else:
        logger = root_logger.getChild(name)
    return logger


def update_record(record, level, msg, *args):
    record.levelno = level
    record.levelname = logging_levels[level]
    record.msg = msg
    record.args = args
    ct = time()
    record.created = ct
    record.msecs = (ct - int(ct)) * 1000


def trace_service(level=logging.INFO,
                  debug_info_func=lambda ctrl: '[conn|%d]' % ctrl.conn.connid):
    def wrapper(cls):
        assert level in logging_levels, (level, logging_levels)
        for method in cls.DESCRIPTOR.methods:
            name = method.name
            setattr(cls, name,
                    trace_method(level, debug_info_func)(getattr(cls, name)))
        return cls
    if isinstance(level, str):
        level = logging_names[level]
        return wrapper
    elif isinstance(level, int):
        return wrapper
    else:
        assert issubclass(level, Service), level
        cls, level = level, logging.INFO
        return wrapper(cls)


def trace_method(level=logging.INFO,
                 debug_info_func=lambda ctrl: '[conn|%d]' % ctrl.conn.connid):
    def wrapper(func):
        assert level in logging_levels, (level, logging_levels)
        co = func.__code__
        full_name = co.co_name
        if isinstance(func, MethodType):
            full_name = '%s.%s' % (func.im_class.DESCRIPTOR.name, full_name)

        # name, level, fn, lno, msg, args, exc_info, func
        record = logging.LogRecord(
            '', level, co.co_filename, co.co_firstlineno, '', (), None,
            full_name
        )

        @wraps(func)
        def _(self, controller, request, done):
            assert isinstance(self, Service)

            start_time = time()
            debug_info = debug_info_func(controller)
            record.name = self.logger.name
            req = repr(str(request))

            def done_wrapper(resp=None, **kwargs):
                update_record(
                    record, level,
                    '%s [rpc|%s] [req|%r] [resp|%r] [time|%.6f]',
                    debug_info, full_name, req, str(kwargs) or str(resp),
                    time() - start_time
                )
                self.logger.handle(record)
                done(resp, **kwargs)
            try:
                return func(self, controller, request, done_wrapper)
            except BaseException as ex:
                if isinstance(ex, Warning):
                    update_record(
                        record, logging.WARN,
                        '%s [rpc|%s] [req|%r] [warning|%s] '
                        '[time|%.6f]',
                        debug_info, full_name, req, ex, time() - start_time
                    )
                else:
                    update_record(
                        record, logging.ERROR,
                        '%s [rpc|%s] [req|%r] [exception|%s] '
                        '[time|%.6f]',
                        debug_info, full_name, req, ex, time() - start_time
                    )
                self.logger.handle(record)
                raise
        return _
    if isinstance(level, str):
        level = logging_names[level]
        return wrapper
    elif isinstance(level, int):
        return wrapper
    else:
        assert callable(level), level
        func, level = level, logging.INFO
        return wrapper(func)


def trace_stub(level=logging.DEBUG, stub=None, stub_name='', request_name=''):
    def wrapper(rpc):
        from pymaid.conf import settings
        if not settings.DEBUG:
            return rpc
        assert level in logging_levels, (level, logging_levels)

        @wraps(rpc)
        def _(request=None, conn=None, broadcaster=None, **kwargs):
            frame = getframe(1)
            stub.logger.handle(LogRecord(
                stub.logger.name, level, frame.f_code.co_filename,
                frame.f_lineno,
                '[stub|%s][request|%r][kwargs|%r]',
                (stub_name, str(request), str(kwargs)), None, stub_name
            ))
            return rpc(request, conn, broadcaster, **kwargs)
        return _
    if isinstance(level, str):
        level = logging_names[level]
        return wrapper
    elif isinstance(level, int):
        return wrapper
    else:
        assert callable(level), level
        rpc, level = level, logging.DEBUG
        return wrapper(rpc)
