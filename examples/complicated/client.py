# coding=utf-8
from __future__ import print_function
import re
from argparse import ArgumentParser

from pymaid.channel import ClientChannel
from pymaid.core import greenlet_pool, Pool
from pymaid.pb import PBHandler, ServiceStub
from pymaid.websocket.websocket import WebSocket

from .pb_pb2 import Service_Stub

message = u'haha帐号'


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '-c', dest='concurrency', type=int, default=100, help='concurrency'
    )
    parser.add_argument(
        '-r', dest='request', type=int, default=100, help='request per client'
    )
    parser.add_argument(
        '--address', type=str, default='ws://127.0.0.1:8888/',
        help='connect address'
    )

    args = parser.parse_args()
    if re.search(r':\d+$', args.address):
        address, port = args.address.split(':')
        args.address = (address, int(port))
    print(args)
    return args


def wrapper(pid, address, count, message=message):
    conn = channel.connect(address)
    for x in range(count):
        response = service.Test(request, conn=conn).get(30)
        assert response.message.message == message, response.message.message
    conn.close()


channel = ClientChannel(PBHandler(), WebSocket)
service = ServiceStub(Service_Stub(None))
method = service.stub.DESCRIPTOR.FindMethodByName('Test')
request_class = service.stub.GetRequestClass(method)
request = request_class(message={'message': message}, count=5)


def main(args):
    pool = Pool()
    # pool.spawn(wrapper, 111111, 10000)
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
