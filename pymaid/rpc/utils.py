import logging

from functools import wraps
from logging import LogRecord
from sys import _getframe as getframe
from time import time
from types import MethodType

from google.protobuf.service import Service

logging_levels = logging._levelToName
logging_names = logging._nameToLevel


def implall(service):
    service_name = service.DESCRIPTOR.name
    missing = []
    for base in service.__bases__:
        for method in base.DESCRIPTOR.methods:
            method_name = method.name
            base_method = getattr(base, method_name)
            impl_method = getattr(service, method_name, base_method)
            if base_method == impl_method:
                missing.append(f'{service_name}.{method_name}')
    if missing:
        raise RuntimeError(f'{missing} are not implemented')
    return service


def update_record(record, level, msg, *args):
    record.levelno = level
    record.levelname = logging_levels[level]
    record.msg = msg
    record.args = args
    ct = time()
    record.created = ct
    record.msecs = (ct - int(ct)) * 1000


def trace_service(level=logging.INFO,
                  debug_info_func=lambda ctrl: f'[conn|{ctrl.conn.connid}]'):
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
            full_name = f'{func.im_class.DESCRIPTOR.name}.{full_name}'

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
                        '%s [rpc|%s] [req|%r] [warning|%s] [time|%.6f]',
                        debug_info, full_name, req, ex, time() - start_time
                    )
                else:
                    update_record(
                        record, logging.ERROR,
                        '%s [rpc|%s] [req|%r] [exception|%s] [time|%.6f]',
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


def trace_stub(level=logging.DEBUG):
    def wrapper(method):
        from pymaid.conf import settings
        if not settings.get('DEBUG', False, ns='pymaid'):
            return method
        assert level in logging_levels, (level, logging_levels)

        @wraps(method)
        def _(
            self,
            request=None,
            *,
            transport=None,
            broadcaster=None,
            protocol=None,
            **kwargs
        ):
            frame = getframe(1)
            method.logger.handle(LogRecord(
                method.logger.name,
                level,
                frame.f_code.co_filename,
                frame.f_lineno,
                '[stub|%s][request|%r][kwargs|%r]',
                (method.name, str(request), str(kwargs)),
                None,
                method.name,
            ))
            return method(
                self, request, transport, broadcaster, protocol, **kwargs
            )
        return _
    if isinstance(level, str):
        level = logging_names[level]
        return wrapper
    elif isinstance(level, int):
        return wrapper
    else:
        assert callable(level), level
        method, level = level, logging.DEBUG
        return wrapper(method)
