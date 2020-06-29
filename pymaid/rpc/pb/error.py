from pymaid.rpc.error import RPCError


PBError = RPCError.create_manager('PBError')
PBError.add_error('RPCNotFound', 'rpc not found')
PBError.add_error(
    'HeartbeatTimeout', '[host|{}][peer|{}] peer heartbeat timeout'
)
PBError.add_error('PacketTooLarge', '[packet_length|{}] out of limitation')
PBError.add_error('EOF', 'socket received eof')
PBError.add_error('Timeout', 'socket read/readline timeout {}')
PBError.add_error('InvalidTransmissionID', 'transmission_id value is invalid')
