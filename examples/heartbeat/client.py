from __future__ import print_function
import re
from argparse import ArgumentParser

from gevent import sleep

from pymaid.channel import ClientChannel
from pymaid.hub import greenlet_pool
from pymaid.pb import PBHandler

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
    for x in range(args.concurrency):
        greenlet_pool.spawn(wrapper, x, args.address, args.sleep_time)

    try:
        greenlet_pool.join()
    except Exception:
        import traceback
        traceback.print_exc()
        print(len(channel.connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    args = parse_args()
    main(args)
