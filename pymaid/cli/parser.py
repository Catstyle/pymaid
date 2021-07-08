import argparse

from pymaid import __version__
from pymaid.conf import settings


class ArgumentParser(argparse.ArgumentParser):

    def __init__(self, *args, **kwargs):
        self.name = kwargs.pop('name', '')
        self.on_parse = kwargs.pop('on_parse', None)
        super().__init__(*args, **kwargs)
        self.subparsers = None

    def create_subparser(
        self,
        name: str,
        **kwargs,
    ):
        group = self.name
        if not self.subparsers:
            self.subparsers = self.add_subparsers(
                title=f'{group} subcommands' if group else 'subcommands',
                dest=f'{group}_subcmd' if group else 'subcmd',
            )

        sub = self.subparsers.add_parser(
            name,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            **kwargs,
        )
        sub.name = f'{group}_{name}' if group else name
        return sub

    def parse_args(self, args=None, namespace=None):
        args = super().parse_args(args, namespace)
        self.on_parse_callback(args)
        return args

    def on_parse_callback(self, args):
        if self.on_parse:
            self.on_parse(args)
        if self.subparsers:
            subcmd = self.get_subcmd(args)
            if subcmd:
                sub_parser = self.subparsers._name_parser_map[subcmd]
                sub_parser.on_parse_callback(args)

    def get_subcmd(self, args):
        subcmd_name = f'{self.name}_subcmd' if self.name else 'subcmd'
        return getattr(args, subcmd_name, None)


def get_parser():
    return parser


def on_parse(args):
    if args.conf:
        settings.load_from_cli(args.conf)
    if args.debug:
        settings.set('DEBUG', True, ns='pymaid')
    if args.loop:
        settings.set('EVENT_LOOP', args.loop, ns='pymaid')
    if args.log_level:
        value = settings.pymaid.LOGGING
        for logger in value['loggers'].values():
            logger['level'] = args.log_level
        settings.set('LOGGING', value, ns='pymaid')


parser = ArgumentParser(
    prog='pymaid',
    description='pymaid, a handy toolset',
    usage='%(prog)s [options]',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    on_parse=on_parse,
)
parser.add_argument(
    '--version', action='version', version=f'%(prog)s {__version__}',
)
parser.add_argument('--debug', action='store_true', help='enable debug mode')
parser.add_argument(
    '--loop',
    choices=('vanilla', 'uvloop'),
    default='uvloop',
    help='set the event loop policy, default is uvloop for better performance',
)
parser.add_argument(
    '--conf',
    type=str,
    action='append',
    help='set conf, format like NS__KEY=TYPE::VALUE; e.g. USER__AGE=int::18',
)
parser.add_argument(
    '--log-level',
    choices=('FATAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'),
    default=settings.pymaid.LOGGING['loggers']['pymaid']['level'],
    help='set logging level',
)
