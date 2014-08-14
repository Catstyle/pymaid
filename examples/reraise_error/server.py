from gevent import wait

from pymaid.channel import Channel
from pb.rpc_pb2 import RemoteError
from error import PlayerNotExist


class RemoteErrorImpl(RemoteError):

    def player_not_exist(self, controller, request, done):
        raise PlayerNotExist

def main():
    channel = Channel()
    channel.listen("127.0.0.1", 8888)
    channel.append_service(RemoteErrorImpl())
    wait()

if __name__ == "__main__":
    main()
