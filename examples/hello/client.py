from gevent.pool import Pool

from pymaid.channel import Channel
from pymaid.agent import ServiceAgent
from hello_pb2 import HelloService_Stub


def wrapper(pid, n):
    conn = channel.connect("127.0.0.1", 8888)
    for x in xrange(n):
        response = service.Hello(conn=conn)
        assert response.message == 'from pymaid', response.message
    conn.close()


channel = Channel()
service = ServiceAgent(HelloService_Stub(channel), conn=None)
def main():
    pool = Pool()
    #pool.spawn(wrapper, 111111, 30000)
    for x in xrange(30000):
        pool.spawn(wrapper, x, 1)

    try:
        pool.join()
    except:
        print len(channel.pending_results)
        print len(channel._outcome_connections)
        print len(channel._income_connections)
    #assert len(channel.pending_results) == 0, channel.pending_results
    #assert len(channel._outcome_connections) == 0, channel._outcome_connections
    #assert len(channel._income_connections) == 0, channel._income_connections

if __name__ == "__main__":
    main()
