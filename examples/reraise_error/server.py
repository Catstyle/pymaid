from pymaid.channel import Channel
from pb.rpc_pb2 import RemoteError
from error import PlayerNotExist


class RemoteErrorImpl(RemoteError):

    def player_profile(self, controller, request, callback):
        raise PlayerNotExist


def main():
    channel = Channel()
    channel.listen("127.0.0.1", 8888)
    channel.append_service(RemoteErrorImpl())
    channel.serve_forever()


if __name__ == "__main__":
    main()
