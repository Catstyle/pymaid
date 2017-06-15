from __future__ import print_function
import re
from argparse import ArgumentParser

import pymaid
from pymaid.channel import ServerChannel
from pymaid.pb import Listener, PBHandler

from rpc_pb2 import RemoteError
from error import PlayerNotExist


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '--address', type=str, default='/tmp/pymaid_reraise.sock',
        help='listen address'
    )

    args = parser.parse_args()
    if re.search(r':\d+$', args.address):
        address, port = args.address.split(':')
        args.address = (address, int(port))
    print(args)
    return args


class RemoteErrorImpl(RemoteError):

    def player_profile(self, controller, request, callback):
        raise PlayerNotExist()


def main(args):
    listener = Listener()
    listener.append_service(RemoteErrorImpl())
    channel = ServerChannel(PBHandler(listener))
    channel.listen(args.address)
    channel.start()
    pymaid.serve_forever()


if __name__ == "__main__":
    args = parse_args()
    main(args)
