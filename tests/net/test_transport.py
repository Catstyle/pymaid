import socket

import pytest

from pymaid.rpc.connection import Connection

from tests.common.models import _TestStream


@pytest.mark.asyncio
async def test_transport_init():
    class T(_TestStream):

        def init(self):
            self.test_init = True

    sock1, sock2 = socket.socketpair(socket.AF_UNIX.value)
    s1, s2 = T(sock1), T(sock2)

    assert s1.test_init
    assert s2.test_init


def test_transport_pipeline():
    Cls = _TestStream | Connection

    assert issubclass(Cls, Connection)
    assert issubclass(Cls, _TestStream)

    # cannot pipeline the reversed order
    with pytest.raises(RuntimeError):
        Cls = Connection | _TestStream

    # Cls already pipelined
    with pytest.raises(RuntimeError):
        Cls = _TestStream | Cls

    with pytest.raises(RuntimeError):
        Cls = _TestStream | Cls

    with pytest.raises(RuntimeError):
        Cls = Cls | Cls
