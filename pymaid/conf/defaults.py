DEBUG = False

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': (
                u'%(asctime)s.%(msecs).03d %(levelname)s '
                '[pid|%(process)d] %(message)s'
            ),
            'datefmt': '%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'loggers': {
        'pymaid': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'asyncio': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Sets the maximum number of consecutive accepts that a process may perform
# on a single wake up. High values give higher priority to high connection
# rates, while lower values give higher priority to already established
# connections.
# Default is 64. Note, that in case of multiple working processes on the
# same listening value, it should be set to a lower value.
MAX_ACCEPT = 64
MAX_TASKS = 32

'''
MAX_CONNECTIONS limits the connections
MAX_CONCURRENCY limits the concurrency of *requests*
MAX_METHOD_CONCURRENCY limits the concurrency of *requests* for specified rpc
e.g.:
1. 10000 connections, next new connection will fail
2. 100 connections, one parallelly call 100 different(not the same) async rpcs
   next rpc call will fail (nomatter from new connection or old connections)
3. 1 connection, parallelly call one async rpc for 10000 times
   next the same rpc call from the connection will fail
'''
MAX_CONNECTIONS = 10000
MAX_CONCURRENCY = 10000
MAX_METHOD_CONCURRENCY = 10000

# connection/socket related settings

PM_KEEPALIVE = True
PM_KEEPIDLE = 60
PM_KEEPINTVL = 5
PM_KEEPCNT = 3

PM_WEBSOCKET_TIMEOUT = 15

SO_SNDBUF = 512 * 1024
SO_RCVBUF = 512 * 1024
SO_SNDTIMEO = 30
SO_RCVTIMEO = 30
