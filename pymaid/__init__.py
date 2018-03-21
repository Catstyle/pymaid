import sys
import os

from . import channel
from . import connection
from . import websocket
from . import pb
from . import pool
from . import error
from . import utils
from . import conf

__all__ = [
    'channel', 'connection', 'websocket', 'pb', 'pool', 'error', 'utils',
    'conf', 'serve_forever'
]

__version__ = '0.3.8.post2'

if 'linux' in sys.platform or 'darwin' in sys.platform:
    # if 'ares' not in os.environ.get('GEVENT_RESOLVER', ''):
    #     sys.stdout.write(
    #         'ares-resolver is better, just `export GEVENT_RESOLVER=ares`\n'
    #     )
    if os.environ.get('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION') != 'cpp':
        sys.stdout.write(
            'C++ implementation protocol buffer has overall performance, see'
            'https://github.com/google/protobuf/blob/master/python/README.md\n'
        )
del os, sys


def serve_forever():
    import gevent
    gevent.wait()
