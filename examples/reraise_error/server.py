import pymaid
from pymaid.pb.channel import PBChannel
from rpc_pb2 import RemoteError
from error import PlayerNotExist


class RemoteErrorImpl(RemoteError):

    def player_profile(self, controller, request, callback):
        raise PlayerNotExist


def main():
    channel = PBChannel()
    channel.listen("127.0.0.1", 8888)
    channel.append_service(RemoteErrorImpl())
    channel.start()
    pymaid.serve_forever()


if __name__ == "__main__":
    main()
