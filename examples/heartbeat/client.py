from __future__ import print_function
import re
from argparse import ArgumentParser

from gevent.pool import Pool
from gevent import sleep

from pymaid.channel import ClientChannel
from pymaid.pb import PBHandler
from pymaid.utils import greenlet_pool

channel = ClientChannel(PBHandler())


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '-c', dest='concurrency', type=int, default=100, help='concurrency'
    )
    parser.add_argument(
        '-s', dest='sleep_time', type=int, default=5, help='wait for heartbeat'
    )
    parser.add_argument(
        '--address', type=str, default='/tmp/pymaid_heartbeat.sock',
        help='connect address'
    )

    args = parser.parse_args()
    if re.search(r':\d+$', args.address):
        address, port = args.address.split(':')
        args.address = (address, int(port))
    print(args)
    return args


def wrapper(pid, address, sleep_time):
    channel.connect(address)
    sleep(sleep_time)


def main(args):
    pool = Pool()
    for x in range(args.concurrency):
        pool.spawn(wrapper, args.address, args.sleep_time)

    try:
        pool.join()
    except:
        import traceback
        traceback.print_exc()
        print(len(channel.connections))
        print(pool.size, len(pool.greenlets))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    args = parse_args()
    main(args)
