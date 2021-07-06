import json

from pymaid.conf import settings

from .parser import get_parser


def entry(args):
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


parser = get_parser().create_subparser('conf', help='show settings data')
parser.add_argument(
    '--list-ns',
    action='store_true',
    help='show the namespaces of settings',
)
parser.add_argument(
    '--ns',
    type=str,
    help='only show the settings of specified namespace',
)
parser.add_argument(
    '--list-types',
    action='store_true',
    help='show the available types for conf',
)
parser.add_argument(
    '--format',
    choices=('json', 'py'),
    default='json',
    help='specify the output format',
)
parser.set_defaults(entry=entry)
