from argparse import ArgumentParser
import re


def get_server_parser():
    parser = ArgumentParser()
    parser.add_argument(
        '--address', type=str, default='/tmp/pymaid.sock',
        help='listen address',
    )
    # parser.add_argument(
    #     '--uvloop', action='store_true', default=False, help='use uvloop'
    # )
    return parser


def get_client_parser():
    parser = ArgumentParser()
    parser.add_argument(
        '-c', dest='concurrency', type=int, default=100, help='concurrency',
    )
    parser.add_argument(
        '-r', dest='request', type=int, default=100, help='request per client',
    )
    parser.add_argument(
        '--address', type=str, default='/tmp/pymaid.sock',
        help='connect address',
    )
    parser.add_argument(
        '--timeout', type=int, default=60,
        help='timeout, in seconds',
    )
    # parser.add_argument(
    #     '--uvloop', action='store_true', default=False, help='use uvloop',
    # )
    return parser


def parse_args(parser):
    args = parser.parse_args()
    if re.search(r':\d+$', args.address):
        address, port = args.address.split(':')
        args.address = (address, int(port))
    print(args)
    # if args.uvloop:
    #     import uvloop
    #     uvloop.install()
    return args
