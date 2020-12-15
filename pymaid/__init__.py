from . import conf
from . import error
from . import net
from . import utils

from .core import *  # noqa

__all__ = ('conf', 'error', 'net', 'utils')

__version__ = '1.0.0a1'

if not conf.settings.get('NO_UVLOOP', ns='pymaid'):
    import uvloop
    uvloop.install()
