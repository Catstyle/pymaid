from __future__ import print_function
import re
from argparse import ArgumentParser

import pymaid
from pymaid.channel import ServerChannel
from pymaid.websocket.websocket import WebSocket
from pymaid.pb import PBHandler, Listener
from pymaid.utils import greenlet_pool

from echo_pb2 import Message, EchoService


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '--address', type=str, default='127.0.0.1:8888', help='listen address'
    )

    args = parser.parse_args()
    if re.search(r':\d+$', args.address):
        address, port = args.address.split(':')
        args.address = (address, int(port))
    print(args)
    return args


class EchoServiceImpl(EchoService):

    def echo(self, controller, request, callback):
        response = Message()
        response.CopyFrom(request)
        callback(response)


def main(args):
    listener = Listener()
    listener.append_service(EchoServiceImpl())
    channel = ServerChannel(PBHandler(listener), WebSocket)
    channel.listen(args.address)
    channel.start()
    try:
        pymaid.serve_forever()
    except:
        import traceback
        traceback.print_exc()
        print(len(channel.connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    args = parse_args()
    main(args)
