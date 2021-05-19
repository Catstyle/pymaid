from socket import error as socket_error
from struct import Struct

st_H = Struct('!H')
pack_H = st_H.pack


class WebSocketError(socket_error):
    '''Base class for all websocket errors.'''


class ProtocolError(WebSocketError):
    '''Raised if an error occurs when de/encoding the websocket protocol.'''

    def __init__(self, reason='', code=1002):
        self.code = code
        self.reason = reason
        self.payload = pack_H(code) + reason.encode('utf-8')
