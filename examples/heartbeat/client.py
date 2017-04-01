from __future__ import print_function
from gevent.pool import Pool
from gevent import sleep

from pymaid.channel import ClientChannel
from pymaid.parser import PBParser
from pymaid.pb import PBHandler
from pymaid.utils import greenlet_pool

channel = ClientChannel(PBHandler(PBParser))


def wrapper(pid, n):
    channel.connect('/tmp/hello_pb.sock')
    sleep(5)


def main():
    pool = Pool()
    for x in range(1000):
        pool.spawn(wrapper, x, 1000)

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
