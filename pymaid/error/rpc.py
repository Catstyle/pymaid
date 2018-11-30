from six import text_type

from .base import ErrorManager


RpcError = ErrorManager.create_manager('RpcError', 13570)
RpcError.add_error('RPCNotExist', 1, text_type('[rpc|{}] not found'))
RpcError.add_error(
    'HeartbeatTimeout', 2,
    text_type('[host|{}][peer|{}] peer heartbeat timeout')
)
RpcError.add_error(
    'PacketTooLarge', 3, text_type('[packet_length|{}] out of limitation')
)
RpcError.add_error('EOF', 4, 'socket received eof')
RpcError.add_error('Timeout', 5, text_type('socket read/readline timeout {}'))
