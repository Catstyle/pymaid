__all__ = [
    'Channel', 'Connection', 'ConnectionPool',
    'pb', 'websocket', 'error', 'utils', 'serve_forever'
]

import sys
import os

from .channel import Channel
from .connection import Connection
from .pools import ConnectionPool
from . import pb
from . import websocket
from . import error
from . import utils


__version__ = '0.3.0'
VERSION = tuple(map(int, __version__.split('.')))


if 'linux' in sys.platform or 'darwin' in sys.platform:
    if 'ares' not in os.environ.get('GEVENT_RESOLVER', ''):
        sys.stdout.write(
            'ares-resolver is better, just `export GEVENT_RESOLVER=ares`\n'
        )
    if os.environ.get('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION') != 'cpp':
        sys.stdout.write(
            'C++ implementation protocol buffer has overall performance, see'
            '`https://github.com/google/protobuf/blob/master/python/README.md#c-implementation`\n'
        )
del os, sys


def serve_forever():
    import gevent
    gevent.wait()
