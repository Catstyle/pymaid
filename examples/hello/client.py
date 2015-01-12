from gevent.pool import Pool

from pymaid.channel import Channel
from pymaid.agent import ServiceAgent
from hello_pb2 import HelloService_Stub
from pymaid.utils import greenlet_pool


def wrapper(pid, n):
    conn = channel.connect("127.0.0.1", 8888, ignore_heartbeat=True)
    for x in xrange(n):
        response = service.Hello(conn=conn)
        assert response.message == 'from pymaid', response.message
    conn.close()


channel = Channel()
service = ServiceAgent(HelloService_Stub(channel), conn=None, profiling=True)
def main():
    import gc
    import sys
    from collections import Counter
    gc.set_debug(gc.DEBUG_LEAK&gc.DEBUG_UNCOLLECTABLE)
    gc.enable()

    pool = Pool()
    pool.spawn(wrapper, 111111, 30000)
    for x in xrange(10000):
        pool.spawn(wrapper, x, 1)

    try:
        pool.join()
    except:
        print len(channel.pending_results)
        print len(channel._outcome_connections)
        print len(channel._income_connections)
        print pool.size, len(pool.greenlets)
        print greenlet_pool.size, len(greenlet_pool.greenlets)

        objects = gc.get_objects()
        print Counter(map(type, objects))
        print
        print Counter({type(obj): sys.getsizeof(obj) for obj in objects})
    else:
        assert len(channel.pending_results) == 0, channel.pending_results
        assert len(channel._outcome_connections) == 0, channel._outcome_connections
        assert len(channel._income_connections) == 0, channel._income_connections
    service.print_summary()

if __name__ == "__main__":
    main()
