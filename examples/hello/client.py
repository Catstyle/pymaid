from gevent.pool import Pool

from pymaid.channel import Channel
from pymaid.agent import ServiceAgent
from hello_pb2 import HelloService_Stub
from pymaid.utils import greenlet_pool


def wrapper(pid, n):
    conn = channel.connect("127.0.0.1", 8888, ignore_heartbeat=True)
    for x in xrange(n):
        response = service.hello(conn=conn)
        assert response.message == 'from pymaid', response.message
    conn.close()


channel = Channel()
service = ServiceAgent(HelloService_Stub(channel), conn=None)
def main():
    import gc
    from collections import Counter
    gc.set_debug(gc.DEBUG_LEAK&gc.DEBUG_UNCOLLECTABLE)
    gc.enable()

    pool = Pool()
    pool.spawn(wrapper, 111111, 10000)
    for x in xrange(200):
        pool.spawn(wrapper, x, 500)

    try:
        pool.join()
    except:
        print len(channel._outcome_connections)
        print len(channel._income_connections)
        print pool.size, len(pool.greenlets)
        print greenlet_pool.size, len(greenlet_pool.greenlets)

        objects = gc.get_objects()
        print Counter(map(type, objects))
    else:
        assert len(channel._outcome_connections) == 0, channel._outcome_connections
        assert len(channel._income_connections) == 0, channel._income_connections
    service.print_summary()

if __name__ == "__main__":
    main()
