import time
import gevent
import GreenletProfiler

from pymaid.channel import Channel
from pymaid.agent import ServiceAgent
from heartbeat_pb2 import LongPlaying_Stub


def main():
    channel = Channel()
    service = ServiceAgent(LongPlaying_Stub(channel))
    conn = channel.connect("127.0.0.1", 8888)

    resp = service.over_two_seconds(conn=conn)
    assert resp
    time.sleep(4)
    # switch greenlet so conn can close
    gevent.sleep(0.1)
    assert conn.is_closed, conn.is_closed

if __name__ == "__main__":
    GreenletProfiler.set_clock_type('cpu')
    GreenletProfiler.start()
    main()
    GreenletProfiler.stop()
    stats = GreenletProfiler.get_func_stats()
    stats.print_all()
