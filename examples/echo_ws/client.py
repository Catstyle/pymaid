from __future__ import print_function

from gevent.pool import Pool

from pymaid.websocket.channel import WSChannel
from pymaid.pb.stub import ServiceStub
from pymaid.utils import greenlet_pool

from echo_pb2 import EchoService_Stub


message = 'a' * 10000
def wrapper(pid, n, message=message):
    conn = channel.connect("ws://127.0.0.1:8888/")
    for x in range(n):
        response = service.echo(request, conn=conn)
        assert response.message == message, len(response.message)
    conn.close()


channel = WSChannel(("127.0.0.1", 8888))
service = ServiceStub(EchoService_Stub(channel))
method = service.stub.DESCRIPTOR.FindMethodByName('echo')
request_class = service.stub.GetRequestClass(method)
request = request_class(message=message)
def main():
    import gc
    from collections import Counter
    gc.set_debug(gc.DEBUG_LEAK&gc.DEBUG_UNCOLLECTABLE)
    gc.enable()

    pool = Pool()
    #pool.spawn(wrapper, 111111, 10000)
    for x in range(10):
        pool.spawn(wrapper, x, 10)

    try:
        pool.join()
    except:
        import traceback
        traceback.print_exc()
        print(len(channel.connections))
        print(pool.size, len(pool.greenlets))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))
    objects = gc.get_objects()
    print(Counter(map(type, objects)))
    print()

if __name__ == "__main__":
    main()
