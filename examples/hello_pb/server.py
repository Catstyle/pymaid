from __future__ import print_function

from pymaid import serve_forever
from pymaid.channel import ServerChannel
from pymaid.parser import PBParser
from pymaid.pb import Listener, PBHandler
from pymaid.utils import greenlet_pool

from hello_pb2 import HelloResponse
from hello_pb2 import HelloService


class HelloServiceImpl(HelloService):

    def hello(self, controller, request, callback):
        response = HelloResponse()
        response.message = "from pymaid"
        callback(response)


def main():
    listener = Listener()
    listener.append_service(HelloServiceImpl())
    channel = ServerChannel(PBHandler(PBParser, listener))
    # channel.listen(('localhost', 8888))
    channel.listen('/tmp/hello_pb.sock')
    channel.start()
    try:
        serve_forever()
    except:
        print(len(channel.connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    main()
