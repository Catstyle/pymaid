from __future__ import print_function
from gevent.pool import Pool

from pymaid.channel import ClientChannel
from pymaid.pb import PBHandler, ServiceStub
from pymaid.utils import greenlet_pool

from echo_pb2 import EchoService_Stub


message = 'a' * 8000


def wrapper(pid, n, message=message):
    conn = channel.connect('/tmp/pymaid_echo.sock')
    for x in range(n):
        response = service.echo(request, conn=conn)
        assert response.message == message, len(response.message)
    conn.close()


channel = ClientChannel(PBHandler())
service = ServiceStub(EchoService_Stub(None))
method = service.stub.DESCRIPTOR.FindMethodByName('echo')
request_class = service.stub.GetRequestClass(method)
request = request_class(message=message)


def main():
    pool = Pool()
    # pool.spawn(wrapper, 111111, 10000)
    for x in range(100):
        pool.spawn(wrapper, x, 10000)

    try:
        pool.join()
    except:
        import traceback
        traceback.print_exc()
        print(pool.size, len(pool.greenlets))
        print(len(channel.connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    main()
