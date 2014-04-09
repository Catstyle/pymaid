from gevent.pool import Pool
import GreenletProfiler

from pymaid.channel import Channel
from pymaid.service_proxy import ServiceProxy
from hello_pb2 import HelloService_Stub


def wrapper(pid, n):
    conn = channel.connect("127.0.0.1", 8888)
    for x in xrange(n):
        response = service.Hello(conn=conn)
        assert response.message == 'from pymaid', response.message
    conn.close()


channel = Channel()
service = ServiceProxy(HelloService_Stub(channel))
def main():
    pool = Pool()
    pool.spawn(wrapper, 111111, 2000)
    for x in xrange(1000):
        pool.spawn(wrapper, x, 1)

    pool.join()
    assert len(channel._pending_results) == 0, channel._pending_results
    assert len(channel._connections) == 0, channel._connections

if __name__ == "__main__":
    GreenletProfiler.set_clock_type('cpu')
    GreenletProfiler.start()
    main()
    GreenletProfiler.stop()
    stats = GreenletProfiler.get_func_stats()
    stats.print_all()
