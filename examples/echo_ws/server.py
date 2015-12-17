from __future__ import print_function

import pymaid
from pymaid.channel import ServerChannel
from pymaid.pb import PBHandler, Listener
from pymaid.utils import greenlet_pool

from echo_pb2 import Message, EchoService


class EchoServiceImpl(EchoService):

    def echo(self, controller, request, callback):
        response = Message()
        response.CopyFrom(request)
        callback(response)


def main():
    listener = Listener()
    listener.append_service(EchoServiceImpl())
    channel = ServerChannel(PBHandler, listener)
    channel.listen(("", 8888))
    channel.start()
    try:
        pymaid.serve_forever()
    except:
        import traceback
        traceback.print_exc()
        print(len(channel.connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    main()
