import logging
import logging.config
import inspect
import sys
import traceback
import warnings

from collections.abc import Mapping

__all__ = ['logger_wrapper', 'get_logger']

pymaid_logger = logging.getLogger('pymaid')


def configure_logging(settings, ns):
    '''Setup logging from pymaid.LOGGING and logging.LOGGING settings.

    Do nothing if `ns` not in (pymaid, logging)
    '''

    if ns not in ('pymaid', 'logging'):
        return

    # Route warnings through python logging
    logging.captureWarnings(True)
    # Allow DeprecationWarnings through the warnings filters
    warnings.simplefilter('default', DeprecationWarning)

    config = settings.get('LOGGING', {}, ns='pymaid')
    for key, value in settings.get('LOGGING', {}, ns='logging').items():
        if not isinstance(value, Mapping):
            config[key] = value
        else:
            config[key].update(value)
    if config:
        if ns == 'pymaid' and settings.pymaid.DEBUG:
            config['loggers']['pymaid']['level'] = True
        logging.config.dictConfig(config)


def logger_wrapper(name=''):

    def _(cls):
        cls.logger = get_logger(name)
        return cls

    if isinstance(name, type):
        cls, name = name, name.__name__
        return _(cls)
    else:
        return _


def get_logger(name):
    return pymaid_logger.getChild(name)


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

    from pymaid import backend
    backend.get_running_loop().add_signal_handler(signum, debug_output)
