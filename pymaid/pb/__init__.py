from struct import Struct

from pymaid.conf import settings

st = Struct(settings.get('PM_PB_HEADER', ns='pymaid'))
header_size = st.size
pack_header = st.pack
unpack_header = st.unpack

from .controller import Controller as PBController  # noqa
from .handler import PBHandler  # noqa
from .listener import Listener  # noqa
from .pymaid_pb2 import Void, Controller, ErrorMessage  # noqa
from .stub import ServiceStub, StubManager  # noqa


__all__ = [
    'PBHandler', 'Listener', 'PBController',
    'ServiceStub', 'StubManager', 'Sender',
    'Void', 'Controller', 'ErrorMessage'
]
