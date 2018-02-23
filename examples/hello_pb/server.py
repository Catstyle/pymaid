from __future__ import print_function
import re
from argparse import ArgumentParser

from pymaid import serve_forever
from pymaid.channel import ServerChannel
from pymaid.hub import greenlet_pool
from pymaid.pb import Listener, PBHandler

from hello_pb2 import HelloResponse
from hello_pb2 import HelloService


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '--address', type=str, default='/tmp/pymaid_hello_pb.sock',
        help='listen address'
    )

    args = parser.parse_args()
    if re.search(r':\d+$', args.address):
        address, port = args.address.split(':')
        args.address = (address, int(port))
    print(args)
    return args


class HelloServiceImpl(HelloService):

    def hello(self, controller, request, callback):
        response = HelloResponse()
        response.message = "from pymaid"
        callback(response)


def main(args):
    listener = Listener()
    listener.append_service(HelloServiceImpl())
    channel = ServerChannel(PBHandler(listener))
    # channel.listen(('localhost', 8888))
    channel.listen(args.address)
    channel.start()
    try:
        serve_forever()
    except Exception:
        print(len(channel.connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    args = parse_args()
    main(args)
