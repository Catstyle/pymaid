import argparse
import importlib
import json
import re
import sys

from pymaid import __version__
from pymaid.conf import settings
from pymaid.core import run

path_to_mod_regex = re.compile(r'(.*)\.py[co]?$')


def entry_run(args):
    if args.main.count(':') != 1:
        print('main entry need to be formatted as `package.module:main_entry`')
        exit(1)
    mod, main = args.main.split(':')
    mod = mod.replace('/', '.')
    if path_to_mod_regex.match(mod):
        mod = path_to_mod_regex.match(mod).group(1)
    mod = importlib.import_module(mod)
    if args.pass_through:
        assert len(args.pass_through) == 1, args.pass_through
        sys.argv = [args.main] + args.pass_through[0]
    run(getattr(mod, main)(*args.args, **args.kwargs))


def entry_conf(args):
    data = settings.namespaces
    if args.list_ns:
        data = list(settings.namespaces)
    elif args.list_types:
        data = list(settings.transformer)
    elif args.ns:
        try:
            data = settings.namespaces[args.ns]
        except KeyError:
            print(
                f'ns `{args.ns}` not found, available namespaces: '
                f'{list(settings.namespaces)}'
            )
            exit(1)

    if args.format == 'json':
        print(json.dumps(data, ensure_ascii=False, indent=4))
    if args.format == 'py':
        import pprint
        pprint.pprint(data)


def create_parser():
    parser = argparse.ArgumentParser(
        prog='pymaid',
        description='pymaid, a useful toolset',
        usage='%(prog)s [options]',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        '--version', action='version', version=f'%(prog)s {__version__}'
    )
    parser.add_argument(
        '--debug', action='store_true', help='enable debug mode',
    )
    parser.add_argument(
        '--loop',
        choices=('vanilla', 'uvloop'),
        default='uvloop',
        help=(
            'specify the event loop policy, '
            'default is uvloop for better performance'
        )
    )
    parser.add_argument(
        '--conf',
        type=str,
        action='append',
        help=(
            'specify settings, format like NS__KEY=TYPE::VALUE; '
            'e.g. USER__AGE=int::18'
        ),
    )
    parser.add_argument(
        '--log-level',
        choices=('FATAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'),
        default=settings.pymaid.LOGGING['loggers']['pymaid']['level'],
        help='set logging level',
    )

    subparsers = parser.add_subparsers(title='subcommands')

    parser_run = subparsers.add_parser(
        'run',
        help='run the entry',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_run.add_argument(
        'main',
        type=str,
        metavar='{package.module:main | path/to/script.py:main}',
        help='main entry',
    )
    parser_run.add_argument(
        '--args',
        type=json.loads,
        default=[],
        help='json formatted args passed to main entry',
    )
    parser_run.add_argument(
        '--kwargs',
        type=json.loads,
        default={},
        help='json formatted kwargs passed to main entry'
    )
    parser_run.add_argument(
        'pass_through',
        action='append',
        nargs='*',
        help=(
            'args directly pass through, '
            'if args startswith -/--, separate with `--`; '
            'e.g. "pymaid run a:main -- 1 2 --main_opt 3"'
        ),
    )
    parser_run.set_defaults(entry=entry_run)

    parser_conf = subparsers.add_parser(
        'conf',
        help='show settings data',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_conf.add_argument(
        '--list-ns',
        action='store_true',
        help='show the namespaces of settings',
    )
    parser_conf.add_argument(
        '--ns',
        type=str,
        help='only show the settings of specified namespace',
    )
    parser_conf.add_argument(
        '--list-types',
        action='store_true',
        help='show the available types for conf',
    )
    parser_conf.add_argument(
        '--format',
        choices=('json', 'py'),
        default='json',
        help='specify the output format',
    )
    parser_conf.set_defaults(entry=entry_conf)
    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    if not hasattr(args, 'entry'):
        parser.print_help()
        exit(0)

    if args.debug:
        print(args)
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
    args.entry(args)


if __name__ == '__main__':
    main()
