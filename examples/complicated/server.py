from __future__ import print_function
import re
from argparse import ArgumentParser

import pymaid
from pymaid.channel import ServerChannel
from pymaid.core import greenlet_pool
from pymaid.pb import PBHandler, Listener
from pymaid.utils import logger
from pymaid.websocket.websocket import WebSocket

from pb_pb2 import Service, Message


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


@logger.trace_service
@logger.logger_wrapper
class ServiceImpl(Service):

    def Test(self, controller, request, callback):
        resp = {
            'message': request.message,
            'uints': range(request.count),
            'messages': {
                idx: Message(**{'message': request.message.message + str(idx)})
                for idx in range(request.count)
            },
        }
        callback(**resp)


def main(args):
    listener = Listener()
    listener.append_service(ServiceImpl())
    channel = ServerChannel(PBHandler(listener), WebSocket)
    channel.listen(args.address)
    channel.start()
    try:
        pymaid.serve_forever()
    except Exception:
        import traceback
        traceback.print_exc()
        print(len(channel.connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    args = parse_args()
    main(args)
