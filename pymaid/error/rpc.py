from .base import Error, Warning

module_index = 10000


class RPCNotExist(Error):

    code = module_index + 1
    message_format = '[rpc|{service_method}] not found'


class ParserNotExist(Error):

    code = module_index + 2
    message_format = '[parser|{parser_type}] not found'


class HeartbeatTimeout(Error):

    code = module_index + 3
    message_format = '[host|{host}][peer|{peer}] peer heartbeat timeout'


class PacketTooLarge(Error):

    code = module_index + 4
    message_format = '[packet_length|{packet_length}] out of limitation'


class EOF(Warning):

    code = module_index + 5
    message_format = 'socket received eof'
