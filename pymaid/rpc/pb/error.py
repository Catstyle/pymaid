from pymaid.rpc.error import RPCError


PBError = RPCError.create_manager('PBError')
PBError.add_error('RPCNotFound', 'rpc not found')
PBError.add_error('InvalidTransmissionID', 'transmission_id value is invalid')
PBError.add_error('InvalidPacketType', 'cannot handle unknown packet')
