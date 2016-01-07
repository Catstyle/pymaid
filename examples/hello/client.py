from __future__ import print_function
from gevent.pool import Pool

from pymaid.channel import ClientChannel
from pymaid.utils import greenlet_pool


req = '1234567890' * 100 + '\n'
req_size = len(req)
channel = ClientChannel()
def wrapper(n):
    conn = channel.connect('/tmp/hello.sock')
    read, write = conn.readline, conn.write
    for x in range(n):
        write(req)
        resp = read(req_size)
        assert resp == req, (len(resp), repr(resp))
    conn.close()


def main():
    pool = Pool()
    for x in range(1000):
        pool.spawn(wrapper, 1000)

    try:
        pool.join()
    except:
        import traceback
        traceback.print_exc()
        print(len(channel.connections))
        print(pool.size, len(pool.greenlets))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    main()
