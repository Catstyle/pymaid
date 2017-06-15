import re
from argparse import ArgumentParser

from gevent.pool import Pool

from pymaid.channel import ClientChannel
from pymaid.pb import ServiceStub, PBHandler

from rpc_pb2 import RemoteError_Stub
from error import PlayerNotExist


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '-c', dest='concurrency', type=int, default=100, help='concurrency'
    )
    parser.add_argument(
        '-r', dest='request', type=int, default=100, help='request per client'
    )
    parser.add_argument(
        '--address', type=str, default='/tmp/pymaid_reraise.sock',
        help='connect address'
    )

    args = parser.parse_args()
    if re.search(r':\d+$', args.address):
        address, port = args.address.split(':')
        args.address = (address, int(port))
    print(args)
    return args


def wrapper(pid, address, count):
    conn = channel.connect(address)
    global cnt
    for x in range(count):
        try:
            service.player_profile(conn=conn, user_id=x)
        except PlayerNotExist:
            cnt += 1
        else:
            assert 'should catch PlayerNotExist'
    conn.close()


cnt = 0
channel = ClientChannel(PBHandler())
service = ServiceStub(RemoteError_Stub(None))


def main(args):
    pool = Pool()
    pool.spawn(wrapper, 111111, 2000)
    for x in range(args.concurrency):
        pool.spawn(wrapper, x, args.address, args.request)

    pool.join()
    assert cnt == 3000


if __name__ == "__main__":
    args = parse_args()
    main(args)
