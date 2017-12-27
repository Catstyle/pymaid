from .base import ErrorManager


RpcError = ErrorManager.create_manager('RpcError', 13570)
RpcError.add_error('RPCNotExist', 1, '[rpc|{}] not found')
RpcError.add_error(
    'HeartbeatTimeout', 2, '[host|{}][peer|{}] peer heartbeat timeout'
)
RpcError.add_error(
    'PacketTooLarge', 3, '[packet_length|{}] out of limitation'
)
RpcError.add_error('EOF', 4, 'socket received eof')
RpcError.add_error('Timeout', 5, 'socket read/readline timeout {}')
