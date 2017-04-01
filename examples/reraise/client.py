from gevent.pool import Pool

from pymaid.channel import ClientChannel
from pymaid.parser import PBParser
from pymaid.pb import ServiceStub, PBHandler

from rpc_pb2 import RemoteError_Stub
from error import PlayerNotExist


def wrapper(pid, n):
    conn = channel.connect(("127.0.0.1", 8888))
    global cnt
    for x in range(n):
        try:
            service.player_profile(conn=conn, user_id=x)
        except PlayerNotExist:
            cnt += 1
        else:
            assert 'should catch PlayerNotExist'
    conn.close()


cnt = 0
channel = ClientChannel(PBHandler(PBParser))
service = ServiceStub(RemoteError_Stub(None))


def main():
    pool = Pool()
    pool.spawn(wrapper, 111111, 2000)
    for x in range(1000):
        pool.spawn(wrapper, x, 1)

    pool.join()
    assert cnt == 3000


if __name__ == "__main__":
    main()
