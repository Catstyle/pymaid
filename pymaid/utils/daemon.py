import atexit
import fcntl
import io
import json
import multiprocessing
import os
import sys
import tempfile
import time

from functools import partial
from pathlib import Path
from psutil import pid_exists
from typing import Callable

from pymaid.utils.logger import get_logger

logger = get_logger('daemon')


def redirect_streams(stdin: str, stdout: str, stderr: str):
    '''Redirect stdin/stdout/stderr streams to the passed files'''
    sys.stdout.flush()
    sys.stderr.flush()

    si = Path(stdin)
    if not si.exists():
        si.parent.mkdir(0o700, parents=True, exist_ok=True)
        si.touch()
    si = si.open('r')

    so = Path(stdout)
    if not so.exists():
        so.parent.mkdir(0o700, parents=True, exist_ok=True)
        so.touch()
    so = so.open('a+')

    se = Path(stderr)
    if not se.exists():
        se.parent.mkdir(0o700, parents=True, exist_ok=True)
        se.touch()
    se = se.open('ab+', 0)

    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())


def cleanup(
    name: str,
    pid_path: Path,
    pid_file: io.FileIO,
    stdin: str,
    stdout: str,
    stderr: str,
    clean_stream_files: bool = False,
):
    logger.info(
        f'[daemon] cleanup [name|{name}][pid_path|{pid_path}]'
        f'[stdin|{stdin}][stdout|{stdout}][stderr|{stderr}]'
    )
    fcntl.lockf(pid_file.fileno(), fcntl.LOCK_UN)
    pid_path.unlink(True)
    unrecord_worker([name])
    if clean_stream_files:
        for name in (stdin, stdout, stderr):
            Path(name).unlink(True)


def record_worker(workers):
    account_book = Path(f'{tempfile.gettempdir()}/workers')
    if not account_book.exists():
        account_book.touch()
    records = json.loads(account_book.read_text() or '{}')
    records.update(workers)
    account_book.write_text(json.dumps(records))


def unrecord_worker(workers):
    account_book = Path(f'{tempfile.gettempdir()}/workers')
    if not account_book.exists():
        account_book.touch()
    records = json.loads(account_book.read_text() or '{}')
    for key in workers:
        records.pop(key, None)
    account_book.write_text(json.dumps(records))


def list_worker():
    account_book = Path(f'{tempfile.gettempdir()}/workers')
    if not account_book.exists():
        account_book.touch()
    return json.loads(account_book.read_text() or '{}')


def _daemonize(
    name: str,
    index: int,
    cwd: str,
    queue,
    donot_exist: bool = False,
):
    '''
    do the UNIX double-fork magic, see Stevens' "Advanced
    Programming in the UNIX Environment" for details (ISBN 0201563177)
    http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16

    :params donot_exist: return instead of exit
    :returns: True if donot_exist
    '''
    try:
        pid = os.fork()
        if pid > 0:
            if donot_exist:
                return False
            # exit first parent
            sys.exit(0)
    except OSError as e:
        sys.stderr.write('fork #1 failed: %d (%s)\n' % (e.errno, e.strerror))
        sys.exit(1)

    # decouple from parent environment
    os.chdir(cwd)
    os.setsid()
    os.umask(0)

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent
            sys.exit(0)
    except OSError as e:
        sys.stderr.write('fork #2 failed: %d (%s)\n' % (e.errno, e.strerror))
        sys.exit(1)

    prefix = f'{cwd}/{name}-{index}'

    stdin = f'{prefix}-stdin'
    stdout = f'{prefix}-stdout'
    stderr = f'{prefix}-stderr'
    try:
        pid = os.getpid()
        # write pidfile; add exclusive lock
        pid_path = Path(f'{prefix}-pid')
        if not pid_path.exists():
            pid_path.parent.mkdir(0o700, parents=True, exist_ok=True)
            pid_path.touch()
        pid_path.write_text('%s' % pid)
        pid_file = pid_path.open()
        fcntl.flock(pid_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        # output to pymaid console script std
        # logger.info(
        #     f'[pymaid|daemonize] [pid|{pid}][cwd|{cwd}]'
        #     f'[stdin|{stdin}][stdout|{stdout}][stderr|{stderr}]'
        # )

        # redirect standard file descriptors
        redirect_streams(stdin, stdout, stderr)

        atexit.register(
            partial(
                cleanup, name, pid_path, pid_file, stdin, stdout, stderr, False
            )
        )
        ok = True
        message = 'ok'
    except Exception as ex:
        ok = False
        message = str(ex)

    queue.put(
        {
            f'{name}-{index}': {
                'index': index, 'pid': pid, 'ok': ok, 'message': message,
            }
        }
    )
    del queue

    return ok


def daemonize(entry: Callable, name: str, count: int = 1):
    assert callable(entry), entry
    tmp_dir = Path(f'{tempfile.gettempdir()}/{name}/')
    if not tmp_dir.exists():
        tmp_dir.mkdir(0o700, parents=True)

    queue = multiprocessing.Queue()
    for idx in range(count):
        key = f'{name}-{idx}'
        if _daemonize(
            name,
            idx,
            tmp_dir,
            queue,
            donot_exist=True,
        ):
            entry()
            # exit forked process
            exit(0)

    logger.info('[pymaid|daemon] getting worker processes info')
    workers = {}
    for idx in range(count):
        try:
            info = queue.get(timeout=1)
        except multiprocessing.queues.Empty:
            logger.info(
                f'[pymaid|daemon][count|{idx + 1}] get worker info timeout'
            )
        else:
            workers.update(info)
    logger.info(f'[pymaid|daemon][worker|{workers}]')
    del queue

    logger.info('[pymaid|daemon] checking worker processes status')

    succeeded = {}
    failed = {}
    while len(succeeded) + len(failed) != count:
        time.sleep(0.2)
        for idx in range(count):
            key = f'{name}-{idx}'
            if key in succeeded or key in failed:
                continue
            info = workers.get(key)
            if not info:
                failed[key] = 'not started'
                continue

            if info['ok']:
                if pid_exists(info['pid']):
                    succeeded[key] = info
                else:
                    try:
                        with open(f'{tmp_dir}/{key}-stderr', 'rb') as fp:
                            fp.seek(-256, 2)
                            err = '...' + fp.read().decode('utf-8')
                    except FileNotFoundError:
                        err = 'err not found'
                    failed[key] = err
            else:
                failed[key] = info['message']
    logger.info(
        f'[pymaid|daemon] workers [succeeded|{succeeded}][failed|{failed}]'
    )
    record_worker(succeeded)
