from pymaid.error import ErrorManager


MonitorError = ErrorManager.create_manager('MonitorError')
MonitorError.add_error(
    'HeartbeatTimeout', 'has not received heartbeat notification in time'
)
