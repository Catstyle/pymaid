from __future__ import absolute_import

import struct


HEADER = '!I'
HEADER_LENGTH = struct.calcsize(HEADER)
LINGER_PACK = struct.pack('ii', 1, 0)


header_struct = struct.Struct(HEADER)
