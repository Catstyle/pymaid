from __future__ import print_function
from gevent import sleep
from gevent.pool import Pool

from pymaid.channel import BidChannel
from pymaid.parser import PBParser
from pymaid.pb import Listener, PBHandler, ServiceStub
from pymaid.utils import greenlet_pool

from chat_pb2 import ChatService_Stub, ChatBroadcast

message = 'a' * 512


class ChatBroadcastImpl(ChatBroadcast):

    def Publish(self, controller, request, done):
        assert request.message == message, len(request.message)
        controller.conn.count += 1


def prepare():
    conn = channel.connect(("127.0.0.1", 8888))
    conn.count = 0
    service.Join(conn=conn)
    connections.append(conn)


def cleanup():
    for conn in connections:
        service.Leave(conn=conn)
        conn.close()


def wrapper(conn, n, total, message=message):
    for x in range(n):
        service.Publish(request, conn=conn)
    while conn.count != total:
        sleep(0.001)


listener = Listener()
listener.append_service(ChatBroadcastImpl())
channel = BidChannel(PBHandler, listener, parser=PBParser)
connections = []

service = ServiceStub(ChatService_Stub(None))
method = service.stub.DESCRIPTOR.FindMethodByName('Publish')
request = service.stub.GetRequestClass(method)(message=message)


def main():
    pool = Pool()
    concurrency, times = 100, 100
    total = concurrency * times
    for x in range(concurrency):
        pool.spawn(prepare)
    pool.join()
    for conn in connections:
        pool.spawn(wrapper, conn, times, total)

    try:
        pool.join()
    except:
        import traceback
        traceback.print_exc()
        print(pool.size, len(pool.greenlets))
        print(len(channel.connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))
    finally:
        cleanup()


if __name__ == "__main__":
    main()
