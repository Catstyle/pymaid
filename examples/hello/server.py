from __future__ import print_function

from pymaid.channel import Channel
from pymaid.utils import greenlet_pool

from hello_pb2 import HelloResponse
from hello_pb2 import HelloService


class HelloServiceImpl(HelloService):

    def hello(self, controller, request, callback):
        response = HelloResponse()
        response.message = "from pymaid"
        callback(response)

def main():
    import gc
    from collections import Counter
    gc.set_debug(gc.DEBUG_LEAK&gc.DEBUG_UNCOLLECTABLE)
    gc.enable()

    channel = Channel()
    channel.listen("127.0.0.1", 8888)
    channel.append_service(HelloServiceImpl())
    channel.enable_heartbeat(10, 3)
    try:
        channel.serve_forever()
    except:
        print(len(channel._outcome_connections))
        print(len(channel._income_connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))

        objects = gc.get_objects()
        print(Counter(map(type, objects)))

if __name__ == "__main__":
    main()
