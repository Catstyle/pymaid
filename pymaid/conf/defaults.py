DEBUG = False

PYMAID_LOGGING = {
    'version': 1,
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
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'loggers': {
        'root': {
            'handlers': ['console'],
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

PM_KEEPALIVE = True
PM_KEEPIDLE = 30
PM_KEEPINTVL = 10
PM_KEEPCNT = 3
