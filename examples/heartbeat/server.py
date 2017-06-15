from __future__ import print_function
import re
from argparse import ArgumentParser

from pymaid import serve_forever
from pymaid.channel import ServerChannel
from pymaid.pb import Listener, PBHandler
from pymaid.utils import greenlet_pool

from pymaid.apps.monitor.service import MonitorServiceImpl
from pymaid.apps.monitor.middleware import MonitorMiddleware


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '--address', type=str, default='/tmp/pymaid_heartbeat.sock',
        help='listen address'
    )
    parser.add_argument(
        '-n', dest='count', default=3, type=int, help='heartbeat max count'
    )
    parser.add_argument(
        '-i', dest='interval', default=1, type=int, help='heartbeat interval'
    )

    args = parser.parse_args()
    if re.search(r':\d+$', args.address):
        address, port = args.address.split(':')
        args.address = (address, int(port))
    print(args)
    return args


def main(args):
    listener = Listener()
    listener.append_service(MonitorServiceImpl())
    channel = ServerChannel(PBHandler(listener))
    channel.listen(args.address)
    channel.append_middleware(MonitorMiddleware(args.interval, args.count))
    channel.start()
    try:
        serve_forever()
    except:
        print(len(channel.connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    args = parse_args()
    main(args)
