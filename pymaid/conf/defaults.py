DEBUG = False

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': (
                u'[%(asctime)s.%(msecs).03d] [%(levelname)s] '
                '[pid|%(process)d] [%(name)s:%(lineno)d] %(message)s'
            ),
            'datefmt': '%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'root': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'loggers': {
        'root': {
            'handlers': ['root'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'pymaid': {
            'handlers': ['console'],
            'level': 'DEBUG',
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
MAX_PACKET_LENGTH = 8 * 1024
MAX_TASKS = 32
MAX_RECV_SIZE = 8 * 1024
MAX_CONCURRENCY = 10000

# connection/socket related settings
PM_PB_HEADER = '!HH'

PM_KEEPALIVE = True
PM_KEEPIDLE = 60
PM_KEEPINTVL = 5
PM_KEEPCNT = 3

PM_WEBSOCKET_TIMEOUT = 15

SO_SNDBUF = 512 * 1024
SO_RCVBUF = 512 * 1024
SO_SNDTIMEO = 30
SO_RCVTIMEO = 30
