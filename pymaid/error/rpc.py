from .base import create_manager


RpcError = create_manager('RpcError', 13570)
RpcError.build_error('RPCNotExist', 1, '[rpc|{}] not found')
RpcError.build_error(
    'HeartbeatTimeout', 2, '[host|{}][peer|{}] peer heartbeat timeout'
)
RpcError.build_error(
    'PacketTooLarge', 3, '[packet_length|{}] out of limitation'
)
RpcError.build_error('EOF', 4, 'socket received eof')
RpcError.build_error('Timeout', 5, 'socket read/readline timeout {}')
