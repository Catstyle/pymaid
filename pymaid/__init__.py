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

from agent import ServiceAgent
from channel import Channel
from controller import Controller
from connection import Connection
from error import Error, Warning
from utils import logger, pool
