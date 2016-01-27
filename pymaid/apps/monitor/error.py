from pymaid.error import Builder


MonitorError = Builder(index=13580)
MonitorError.build_error(
    'HeartbeatTimeout', 1, 'has not received heartbeat notification in time'
)
