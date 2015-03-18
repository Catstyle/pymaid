from __future__ import print_function
from gevent.pool import Pool

from pymaid.channel import Channel
from pymaid.utils import greenlet_pool


def wrapper(pid, n):
    conn = channel.connect('/tmp/hello.sock')
    req = '1234567890' * 100 + '\n'
    req_size = len(req)
    read, write = conn.readline, conn.write
    for x in range(n):
        write(req)
        resp = read(req_size)
        assert resp == req, len(resp)
    conn.close()


channel = Channel()
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
    else:
        assert len(channel.incoming_connections) == 0, channel.incoming_connections
        assert len(channel.outgoing_connections) == 0, channel.outgoing_connections
        objects = gc.get_objects()
        print(Counter(map(type, objects)))
    #profiler.print_stats()
    #service.print_summary()

if __name__ == "__main__":
    main()
