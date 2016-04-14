from pymaid.error import create_manager


MonitorError = create_manager('MonitorError', 13580)
MonitorError.build_error(
    'HeartbeatTimeout', 1, 'has not received heartbeat notification in time'
)
