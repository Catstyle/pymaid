from __future__ import print_function

import pymaid
from pymaid.pb.channel import PBChannel
from pymaid.utils import greenlet_pool

from hello_pb2 import HelloResponse
from hello_pb2 import HelloService


class HelloServiceImpl(HelloService):

    def hello(self, controller, request, callback):
        response = HelloResponse()
        response.message = "from pymaid"
        callback(response)

def main():
    channel = PBChannel()
    channel.listen(('localhost', 8888))
    channel.append_service(HelloServiceImpl())
    channel.start()
    try:
        pymaid.serve_forever()
    except:
        print(len(channel.outgoing_connections))
        print(len(channel.incoming_connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    main()
