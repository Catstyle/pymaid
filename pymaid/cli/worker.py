import importlib
import json
import re
import sys
import tempfile

from pathlib import Path

from psutil import Process, NoSuchProcess

from pymaid.conf import settings
from pymaid.core import run, run_in_processpool, gather
from pymaid.core import CancelledError, ProcessPoolExecutor
from pymaid.utils.daemon import daemonize, list_worker
from pymaid.utils.logger import get_logger

from .parser import get_parser

path_to_mod_regex = re.compile(r'(.*)\.py[co]?$')

logger = get_logger('pymaid')


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
    if args.parallel < 1:
        print(f'-p/--parallel should be positive, got {args.parallel}')
        exit(1)
    if args.parallel > 1:
        # enabled REUSE_PORT for parallel workers
        settings.pymaid.update({'REUSE_PORT': True})

    main_not_call = getattr(mod, main)
    if args.daemon:
        daemonize(
            lambda: run(
                main_not_call(*(args.args or ()), **(args.kwargs or {}))
            ),
            name=args.name or args.main,
            count=args.parallel,
        )
    elif args.parallel == 1:
        run(main_not_call(*args.args, **args.kwargs))
    else:
        async def wrapper():
            executor = ProcessPoolExecutor(args.parallel)
            results = [
                run_in_processpool(
                    run,
                    args=(main_not_call,),
                    kwargs={'args': args.args, 'kwargs': args.kwargs},
                    executor=executor,
                )
                for _ in range(args.parallel)
            ]
            try:
                await gather(*results, return_exceptions=False)
            except (SystemExit, KeyboardInterrupt, CancelledError):
                pass
        run(wrapper())


def stop_worker(pid):
    try:
        p = Process(int(pid))
    except NoSuchProcess:
        logger.warning(f'process {pid} not found')
        return False
    p.terminate()
    return True


def split_index_range(index):
    if index == 'all':
        for value in list_worker().values():
            yield value['index']
        return

    for idx in index.split(','):
        if '-' in idx:
            start, end = [int(i) for i in idx.split('-')]
            yield from range(start, end + 1)
        else:
            yield int(idx)


def entry_stop(args):
    if not args.name:
        print('manage need worker name, missing `--name` ?')
        exit(1)
    name = args.name
    tmp_dir = Path(f'{tempfile.gettempdir()}/{name}/')
    for index in split_index_range(args.index):
        pidfile = Path(f'{tmp_dir}/{name}-{index}-pid')
        if not pidfile.exists():
            logger.warning(f'worker {name}-{index} not found')
            continue
        pid = int(pidfile.read_text())
        ret = stop_worker(pid)
        logger.info(f'worker {name}-{index}|{pid} stopped: {ret}')


def entry_ls(args):
    print(json.dumps(list_worker(), indent=4))


worker_parser = get_parser().create_subparser('worker', help='worker')

parser_run = worker_parser.create_subparser('run', help='run the entry')
parser_run.add_argument(
    'main',
    type=str,
    metavar='{package.module:main | path/to/script.py:main}',
    help='main entry',
)
parser_run.add_argument(
    '--name',
    type=str,
    # default=''.join(random.sample(string.ascii_letters, 6)),
    help='specify worker name, if not set, args.main will be used',
)
parser_run.add_argument(
    '-d',
    '--daemon',
    action='store_true',
    default=False,
    help='run entry in daemon mode',
)
parser_run.add_argument(
    '-p',
    '--parallel',
    type=int,
    default=1,
    help='run entry parallelly',
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

parser_ls = worker_parser.create_subparser('ls', help='list the workers')
parser_ls.set_defaults(entry=entry_ls)

parser_stop = worker_parser.create_subparser(
    'stop', help='stop the worker',
)
parser_stop.add_argument('name', metavar='worker_name', help='worker name')
parser_stop.add_argument(
    'index',
    metavar='worker_index',
    nargs='?',
    default='all',
    help='e.g.: 1,2,3-5',
)
parser_stop.set_defaults(entry=entry_stop)
