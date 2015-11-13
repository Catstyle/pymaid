from .base import error_factory

module_index = 13570


RPCNotExist = error_factory(
    'RPCNotExist', module_index+1, '[rpc|{service_method}] not found'
)


ParserNotExist = error_factory(
    'ParserNotExist', module_index+2, '[parser|{parser_type}] not found'
)


HeartbeatTimeout = error_factory(
    'HeartbeatTimeout', module_index+3,
    '[host|{host}][peer|{peer}] peer heartbeat timeout'
)


PacketTooLarge = error_factory(
    'PacketTooLarge', module_index+4,
    '[packet_length|{packet_length}] out of limitation'
)


EOF = error_factory('EOF', module_index+5, 'socket received eof')
