from gevent.pool import Pool
import GreenletProfiler

from pymaid.channel import Channel
from pymaid.agent import ServiceAgent
from pb.rpc_pb2 import RemoteError_Stub
from error import PlayerNotExist


def wrapper(pid, n):
    conn = channel.connect("127.0.0.1", 8888)
    global cnt
    for x in xrange(n):
        try:
            service.player_not_exist(conn=conn)
        except PlayerNotExist:
            cnt += 1
        else:
            assert 'should catch PlayerNotExist'
    conn.close()

cnt = 0
channel = Channel()
service = ServiceAgent(RemoteError_Stub(channel), conn=None)
def main():
    pool = Pool()
    pool.spawn(wrapper, 111111, 2000)
    for x in xrange(1000):
        pool.spawn(wrapper, x, 1)

    pool.join()
    assert len(channel._pending_results) == 0, channel._pending_results
    assert len(channel._connections) == 0, channel._connections
    assert cnt == 3000

if __name__ == "__main__":
    GreenletProfiler.set_clock_type('cpu')
    GreenletProfiler.start()
    main()
    GreenletProfiler.stop()
    stats = GreenletProfiler.get_func_stats()
    stats.print_all()
