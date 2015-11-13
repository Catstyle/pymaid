from .base import Builder


RpcError = Builder(13570)
RpcError.build_error('RPCNotExist', 1, '[rpc|{service_method}] not found')
RpcError.build_error('ParserNotExist', 2, '[parser|{parser_type}] not found')
RpcError.build_error(
    'HeartbeatTimeout', 3, '[host|{host}][peer|{peer}] peer heartbeat timeout'
)
RpcError.build_error(
    'PacketTooLarge', 4, '[packet_length|{packet_length}] out of limitation'
)
RpcError.build_error('EOF', 5, 'socket received eof')
