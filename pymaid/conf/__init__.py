from __future__ import absolute_import

import warnings
from importlib import import_module

from pymaid.utils.logger import pymaid_logger_wrapper

from . import defaults


@pymaid_logger_wrapper
class Settings(object):

    def __init__(self):
        self.load_from_object(defaults)

    def _configure_logging(self):
        """
        Setup logging from LOGGING_CONFIG and LOGGING settings.
        """
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

        if hasattr(self, 'PYMAID_LOGGING'):
            logging.config.dictConfig(self.PYMAID_LOGGING)
        if hasattr(self, 'LOGGING'):
            logging.config.dictConfig(self.LOGGING)

    def load_from_module(self, module_name):
        """Load the settings module pointed to by the module_name.

        This is used the first time we need any settings at all,
        if the user has not previously configured the settings manually.

        The user can manually configure settings prior to using them.
        """
        try:
            mod = import_module(module_name)
        except ImportError as e:
            raise ImportError(
                "Could not import settings '%s' (Is it on sys.path?): %s" % (
                    module_name, e
                )
            )
        self.load_from_object(mod)

    def load_from_object(self, mod):
        for setting in dir(mod):
            if setting == setting.upper():
                setattr(self, setting, getattr(mod, setting))
        self._configure_logging()
        self.logger.debug(
            '[pymaid][settings] configured [%s]',
            {attr: value for attr, value in self.__dict__.items()
             if attr == attr.upper()}
        )


settings = Settings()
