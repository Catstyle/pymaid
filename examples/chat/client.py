from __future__ import print_function
import re
from argparse import ArgumentParser

from gevent import sleep
from gevent.pool import Pool

from pymaid.channel import ClientChannel
from pymaid.pb import Listener, PBHandler, ServiceStub
from pymaid.utils import greenlet_pool

from chat_pb2 import ChatService_Stub, ChatBroadcast

message = 'a' * 512


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '-c', dest='concurrency', type=int, default=100, help='concurrency'
    )
    parser.add_argument(
        '-r', dest='request', type=int, default=100, help='request per client'
    )
    parser.add_argument(
        '--address', type=str, default='/tmp/pymaid_chat.sock',
        help='connect address'
    )

    args = parser.parse_args()
    if re.search(r':\d+$', args.address):
        address, port = args.address.split(':')
        args.address = (address, int(port))
    print(args)
    return args


class ChatBroadcastImpl(ChatBroadcast):

    def Publish(self, controller, request, done):
        assert request.message == message, len(request.message)
        controller.conn.count += 1


def prepare(address):
    conn = channel.connect(address)
    conn.count = 0
    service.Join(conn=conn).get()
    connections.append(conn)


def cleanup():
    for conn in connections:
        service.Leave(conn=conn).get()
        conn.close()


def wrapper(conn, n, total, message=message):
    for x in range(n):
        service.Publish(request, conn=conn)
    while conn.count != total:
        sleep(0.1)


listener = Listener()
listener.append_service(ChatBroadcastImpl())
channel = ClientChannel(PBHandler(listener))
connections = []

service = ServiceStub(ChatService_Stub(None))
method = service.stub.DESCRIPTOR.FindMethodByName('Publish')
request = service.stub.GetRequestClass(method)(message=message)


def main(args):
    pool = Pool()
    concurrency, request = args.concurrency, args.request
    total = concurrency * request
    for x in range(concurrency):
        pool.spawn(prepare, args.address)
    pool.join()
    for conn in connections:
        pool.spawn(wrapper, conn, request, total)

    try:
        pool.join()
    except Exception:
        import traceback
        traceback.print_exc()
        print(pool.size, len(pool.greenlets))
        print(len(channel.connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))
    finally:
        cleanup()


if __name__ == "__main__":
    args = parse_args()
    main(args)
