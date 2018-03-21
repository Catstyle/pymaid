import logging
import logging.config

import sys
import inspect
import traceback

from collections import Mapping
import warnings

from pymaid.core import signal

__all__ = ['create_project_logger', 'logger_wrapper']

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


def enable_debug_output(signum):

    def debug_output(sig, frame):
        sys.stderr.write('############## pymaid debug_output ##############\n')
        for tid, frame in sys._current_frames().iteritems():
            sys.stderr.write('\n')
            sys.stderr.write('thread: %s\n' % tid)
            sys.stderr.write(
                ''.join(traceback.format_list(traceback.extract_stack(frame)))
            )
            sys.stderr.write('%s' % str(inspect.getargvalues(frame)))
    signal(signum, debug_output)
