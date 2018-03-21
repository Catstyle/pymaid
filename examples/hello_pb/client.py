from __future__ import print_function
import re
from argparse import ArgumentParser

from pymaid.channel import ClientChannel
from pymaid.core import greenlet_pool, Pool
from pymaid.pb import PBHandler, ServiceStub

from hello_pb2 import HelloService_Stub


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '-c', dest='concurrency', type=int, default=100, help='concurrency'
    )
    parser.add_argument(
        '-r', dest='request', type=int, default=100, help='request per client'
    )
    parser.add_argument(
        '--address', type=str, default='/tmp/pymaid_hello_pb.sock',
        help='connect address'
    )

    args = parser.parse_args()
    if re.search(r':\d+$', args.address):
        address, port = args.address.split(':')
        args.address = (address, int(port))
    print(args)
    return args


def wrapper(pid, address, count):
    # conn = channel.connect(('localhost', 8888))
    conn = channel.connect(address)
    for x in range(count):
        response = service.hello(conn=conn).get(30)
        assert response.message == 'from pymaid', response.message
    conn.close()


channel = ClientChannel(PBHandler())
service = ServiceStub(HelloService_Stub(None))


def main(args):
    pool = Pool()
    for x in range(args.concurrency):
        pool.spawn(wrapper, x, args.address, args.request)

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
