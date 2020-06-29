from pymaid.error import ErrorManager


MonitorError = ErrorManager.create_manager('MonitorError', 13580)
MonitorError.add_error(
    'HeartbeatTimeout', 1, 'has not received heartbeat notification in time'
)
