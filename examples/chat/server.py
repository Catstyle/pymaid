from __future__ import print_function

import six
import re
from argparse import ArgumentParser

import pymaid
from pymaid.channel import ServerChannel
from pymaid.core import greenlet_pool
from pymaid.pb import Listener, PBHandler, ServiceStub

from chat_pb2 import ChatService, ChatBroadcast_Stub


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '--address', type=str, default='/tmp/pymaid_chat.sock',
        help='listen address'
    )

    args = parser.parse_args()
    if re.search(r':\d+$', args.address):
        address, port = args.address.split(':')
        args.address = (address, int(port))
    print(args)
    return args


class ChatServiceImpl(ChatService):

    def __init__(self, *args, **kwargs):
        super(ChatServiceImpl, self).__init__(*args, **kwargs)
        self.members = {}
        self.broadcast_stub = ServiceStub(ChatBroadcast_Stub(None))

    def Join(self, controller, request, done):
        conn = controller.conn
        assert conn.connid not in self.members, \
            (conn.connid, self.members.keys())
        self.members[conn.connid] = conn
        done()

    def Publish(self, controller, request, done):
        self.broadcast_stub.Publish(
            request, broadcaster=six.itervalues(self.members)
        )
        done()

    def Leave(self, controller, request, done):
        conn = controller.conn
        assert conn.connid in self.members, (conn.connid, self.members.keys())
        del self.members[conn.connid]
        done()


def main(args):
    listener = Listener()
    listener.append_service(ChatServiceImpl())
    channel = ServerChannel(PBHandler(listener))
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
