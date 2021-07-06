import sys

from . import conf
from . import worker
from .parser import get_parser


__all__ = ['conf', 'worker']


def main():
    parser = get_parser()
    args = parser.parse_args()

    if args.debug:
        print(args)

    if not hasattr(args, 'entry'):
        print(parser.parse_args(sys.argv[1:] + ['-h']))
        exit(1)

    args.entry(args)
