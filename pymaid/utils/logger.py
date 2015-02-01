import logging
import logging.config

__all__ = ['configure_root_logger', 'pymaid_logger_wrapper', 'logger_wrapper']

basic_logging = {
    'version': 1,
    'formatters': {
        'standard': {
            'format': ('[%(asctime)s.%(msecs).03d] [process|%(process)d] '
                       '[%(name)s:%(lineno)d] [%(levelname)s] %(message)s'),
            'datefmt': '%Y-%m-%d %H:%M:%S'
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
        'pymaid': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
logging.config.dictConfig(basic_logging)

pymaid_logger = logging.getLogger('pymaid')
root_logger = None


def configure_root_logger(name):
    global root_logger
    assert not root_logger
    root_logger = logging.getLogger(name)
    return root_logger


def pymaid_logger_wrapper(cls):
    cls.logger = pymaid_logger.getChild(cls.__name__)
    return cls


def logger_wrapper(cls):
    if root_logger:
        cls.logger = root_logger.getChild(cls.__name__)
    else:
        cls.logger = logging.getLogger(cls.__name__)
    return cls
