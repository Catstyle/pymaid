import logging
import logging.config

__all__ = ['configure_project_logger', 'pymaid_logger_wrapper', 'logger_wrapper']

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
    if project_logger:
        cls.logger = project_logger.getChild(cls.__name__)
    else:
        cls.logger = root_logger.getChild(cls.__name__)
    return cls
