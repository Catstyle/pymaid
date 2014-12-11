from __future__ import absolute_import
__all__ = [
    'ServiceAgent', 'Channel', 'Controller', 'Connection',
    'Error', 'Warning', 'logger', 'pool'
]

__version__ = '0.0.1'
VERSION = tuple(map(int, __version__.split('.')))

import sys
if sys.platform.startswith('linux'):
    import os
    os.environ.setdefault('GEVENT_RESOLVER', 'ares')

from pymaid.agent import ServiceAgent
from pymaid.channel import Channel
from pymaid.controller import Controller
from pymaid.connection import Connection
from pymaid.error import Error, Warning
from pymaid.utils import logger, pool
