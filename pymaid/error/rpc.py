from .base import ErrorManager


RpcError = ErrorManager.create_manager('RpcError')
RpcError.add_error('RPCNotFound', 'rpc not found')
RpcError.add_error(
    'HeartbeatTimeout', '[host|{}][peer|{}] peer heartbeat timeout'
)
RpcError.add_error('PacketTooLarge', '[packet_length|{}] out of limitation')
RpcError.add_error('EOF', 'socket received eof')
RpcError.add_error('Timeout', 'socket read/readline timeout {}')
