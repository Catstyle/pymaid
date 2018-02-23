from __future__ import print_function
import re
from argparse import ArgumentParser

from gevent.pool import Pool

from pymaid.channel import ClientChannel
from pymaid.hub import greenlet_pool


req = '1234567890' * 100 + '\n'
req_size = len(req)
channel = ClientChannel()


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '-c', dest='concurrency', type=int, default=100, help='concurrency'
    )
    parser.add_argument(
        '-r', dest='request', type=int, default=100, help='request per client'
    )
    parser.add_argument(
        '--address', type=str, default='/tmp/pymaid_hello.sock',
        help='connect address'
    )

    args = parser.parse_args()
    if re.search(r':\d+$', args.address):
        address, port = args.address.split(':')
        args.address = (address, int(port))
    print(args)
    return args


def wrapper(address, count):
    conn = channel.connect(address)
    read, write = conn.readline, conn.write
    for x in range(count):
        write(req)
        resp = read(req_size)
        assert resp == req, (len(resp), repr(resp))
    conn.close()


def main(args):
    pool = Pool()
    for x in range(args.concurrency):
        pool.spawn(wrapper, args.address, args.request)

    try:
        pool.join()
    except Exception:
        import traceback
        traceback.print_exc()
        print(len(channel.connections))
        print(pool.size, len(pool.greenlets))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    args = parse_args()
    main(args)
