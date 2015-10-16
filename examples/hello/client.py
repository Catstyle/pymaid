from __future__ import print_function
from gevent.pool import Pool

from pymaid.channel import Channel
from pymaid.connection import Connection
from pymaid.utils import greenlet_pool


def wrapper(pid, n):
    conn = Connection.create('/tmp/hello.sock')
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
    pool = Pool()
    #pool.spawn(wrapper, 111111, 10000)
    for x in range(1000):
        pool.spawn(wrapper, x, 1000)

    try:
        pool.join()
    except:
        import traceback
        traceback.print_exc()
        print(len(channel.clients))
        print(pool.size, len(pool.greenlets))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    main()
