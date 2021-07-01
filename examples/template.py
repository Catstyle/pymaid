import atexit
from argparse import ArgumentParser

from pymaid.net.utils.uri import parse_uri
from pymaid.utils.functional import enable_echo


def get_base_parser():
    parser = ArgumentParser()
    parser.add_argument(
        '--address',
        type=str,
        default='unix:///tmp/pymaid.sock',
        help='transport address',
    )
    parser.add_argument(
        '--uvloop', action='store_true', default=False, help='use uvloop'
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        default=False,
        help='print debug info'
    )
    return parser


def get_server_parser():
    parser = get_base_parser()
    parser.add_argument(
        '--backlog', type=int, default=4096, help='listen backlog',
    )
    return parser


def get_client_parser():
    parser = get_base_parser()
    parser.add_argument(
        '-c', dest='concurrency', type=int, default=100, help='concurrency',
    )
    parser.add_argument(
        '-r', dest='request', type=int, default=100, help='request per client',
    )
    parser.add_argument('--msize', type=int, default=1024, help='message size')
    parser.add_argument(
        '--timeout', type=int, default=60, help='timeout, in seconds',
    )
    return parser


def parse_args(parser):
    args = parser.parse_args()
    args.uri = parse_uri(args.address)
    print(args)
    if args.uvloop:
        import uvloop
        uvloop.install()
    if args.verbose:
        args.debug = print
    else:
        def debug(*args, **kwargs):
            pass
        args.debug = debug
    return args


atexit.register(enable_echo, True)
enable_echo(False)
