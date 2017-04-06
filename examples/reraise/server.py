import pymaid
from pymaid.channel import ServerChannel
from pymaid.pb import Listener, PBHandler

from rpc_pb2 import RemoteError
from error import PlayerNotExist


class RemoteErrorImpl(RemoteError):

    def player_profile(self, controller, request, callback):
        raise PlayerNotExist()


def main():
    listener = Listener()
    listener.append_service(RemoteErrorImpl())
    channel = ServerChannel(PBHandler(listener))
    channel.listen(("127.0.0.1", 8888))
    channel.start()
    pymaid.serve_forever()


if __name__ == "__main__":
    main()
