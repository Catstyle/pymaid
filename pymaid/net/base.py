import enum

from pymaid.utils.logger import get_logger

logger = get_logger('net')


class TransportState(enum.IntEnum):

    UNKNOWN = 0
    OPENED = 10
    CONNECTED = 50
    CLOSING = 90
    CLOSED = 100


class ChannelState(enum.IntEnum):

    CREATED = 0
    STARTED = 10
    PAUSED = 20
    SHUTTING_DOWN = 50
    CLOSING = 90
    CLOSED = 100
