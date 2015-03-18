from __future__ import print_function
from gevent.pool import Pool

from pymaid.pb.channel import PBChannel
from pymaid.agent import ServiceAgent
from pymaid.utils import greenlet_pool

from hello_pb2 import HelloService_Stub


def wrapper(pid, n):
    conn = channel.connect(("127.0.0.1", 8888))
    for x in range(n):
        response = service.hello(conn=conn)
        assert response.message == 'from pymaid', response.message
    conn.close()


channel = PBChannel()
service = ServiceAgent(HelloService_Stub(channel))
def main():
    import gc
    from collections import Counter
    gc.set_debug(gc.DEBUG_LEAK&gc.DEBUG_UNCOLLECTABLE)
    gc.enable()

    pool = Pool()
    #pool.spawn(wrapper, 111111, 10000)
    for x in range(200):
        pool.spawn(wrapper, x, 500)

    try:
        pool.join()
    except:
        import traceback
        traceback.print_exc()
        print(len(channel.outgoing_connections))
        print(len(channel.incoming_connections))
        print(pool.size, len(pool.greenlets))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))

        objects = gc.get_objects()
        print(Counter(map(type, objects)))

if __name__ == "__main__":
    main()
