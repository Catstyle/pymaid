from pymaid.error.base import ErrorManager


RPCError = ErrorManager.create_manager('RPCError')
RPCError.add_error('ServerPaused', 'server pause accept new connection')
RPCError.add_error('ConnectionLimit', 'server is full')
RPCError.add_error('RPCRequestSent', '')
RPCError.add_error('RPCRequestReceived', '')
RPCError.add_error('RPCResponseSent', '')
RPCError.add_error('RPCResponseReceived', '')
RPCError.add_error('MultipleRequestForUnaryMethod', '')
RPCError.add_error('MultipleResponseForUnaryMethod', '')
RPCError.add_error('RPCShutdown', '')
