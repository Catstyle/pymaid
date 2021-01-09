import enum

from pymaid.utils.logger import get_logger

logger = get_logger('net')


class TransportState(enum.IntEnum):

    UNKNOWN = 0
    OPENED = 10
    CLOSING = 20
    CLOSED = 30


class ChannelState(enum.IntEnum):

    CREATED = 0
    STARTED = 10
    PAUSED = 20
    CLOSING = 30
    CLOSED = 40
