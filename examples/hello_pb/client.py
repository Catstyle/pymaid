from __future__ import print_function
from gevent.pool import Pool

from pymaid.channel import ClientChannel
from pymaid.parser import PBParser
from pymaid.pb import PBHandler, ServiceStub
from pymaid.utils import greenlet_pool

from hello_pb2 import HelloService_Stub


def wrapper(pid, n):
    # conn = channel.connect(('localhost', 8888))
    conn = channel.connect('/tmp/hello_pb.sock')
    for x in range(n):
        response = service.hello(conn=conn)
        assert response.message == 'from pymaid', response.message
    conn.close()


channel = ClientChannel(PBHandler(PBParser))
service = ServiceStub(HelloService_Stub(None))


def main():
    pool = Pool()
    for x in range(100):
        pool.spawn(wrapper, x, 10000)

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
