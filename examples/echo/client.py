from __future__ import print_function

from gevent.pool import Pool

from pymaid.pb.channel import PBChannel
from pymaid.connection import Connection
from pymaid.agent import ServiceAgent
from pymaid.utils import greenlet_pool

from echo_pb2 import EchoService_Stub

Connection.MAX_PACKET_LENGTH = 1001000


message = 'a' * 1000000
def wrapper(pid, n, message=message):
    conn = channel.connect(("127.0.0.1", 8888))
    for x in range(n):
        response = service.echo(request, conn=conn)
        assert response.message == message, len(response.message)
    conn.close()


channel = PBChannel()
service = ServiceAgent(EchoService_Stub(channel))
method, request_class = service.get_method('echo')
request = request_class(message=message)
def main():
    import gc
    from collections import Counter
    gc.set_debug(gc.DEBUG_LEAK&gc.DEBUG_UNCOLLECTABLE)
    gc.enable()

    pool = Pool()
    #pool.spawn(wrapper, 111111, 10000)
    for x in range(10):
        pool.spawn(wrapper, x, 100)

    try:
        pool.join()
    except:
        print(len(channel.outgoing_connections))
        print(len(channel.incoming_connections))
        print(pool.size, len(pool.greenlets))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))
    objects = gc.get_objects()
    print(Counter(map(type, objects)))
    print()

if __name__ == "__main__":
    main()
