from __future__ import absolute_import
__all__ = [
    'ServiceAgent', 'Channel', 'Connection', 'Controller', 'PBChannel',
    'Error', 'Warning', 'parser', 'logger', 'pool', 'serve_forever'
]
import gevent.monkey
gevent.monkey.patch_all()


import sys

__version__ = '0.2.9'
VERSION = tuple(map(int, __version__.split('.')))


platform = sys.platform
if 'linux' in platform or 'darwin' in platform:
    import os
    if 'ares' not in os.environ.get('GEVENT_RESOLVER', ''):
        sys.stdout.write(
            'ares-resolver is better, just `export GEVENT_RESOLVER=ares`\n'
        )
    if os.environ.get('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION') != 'cpp':
        sys.stdout.write(
            'C++ implementation protocol buffer has overall performance, see'
            '`https://github.com/google/protobuf/blob/master/python/README.md#c-implementation`\n'
        )


from pymaid.channel import Channel
from pymaid.connection import Connection
from pymaid.pb.agent import ServiceAgent
from pymaid.pb.controller import Controller
from pymaid.pb.channel import PBChannel
from pymaid import parser
from pymaid.error import Error, Warning
from pymaid.utils import logger, pool


from gevent import wait
def serve_forever():
    wait()
