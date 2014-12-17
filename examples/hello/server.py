from pymaid.channel import Channel
from hello_pb2 import HelloResponse
from hello_pb2 import HelloService
from pymaid.utils import greenlet_pool


class HelloServiceImpl(HelloService):

    def Hello(self, controller, request, done):
        response = HelloResponse()
        response.message = "from pymaid"
        done(response)

def main():
    import gc
    import sys
    from collections import Counter
    gc.set_debug(gc.DEBUG_LEAK&gc.DEBUG_UNCOLLECTABLE)
    gc.enable()

    channel = Channel()
    channel.listen("127.0.0.1", 8888)
    channel.append_service(HelloServiceImpl())
    channel.enable_heartbeat(5, 3)
    try:
        channel.serve_forever()
    except:
        print len(channel.pending_results)
        print len(channel._outcome_connections)
        print len(channel._income_connections)
        print greenlet_pool.size, len(greenlet_pool.greenlets)

        objects = gc.get_objects()
        print Counter(map(type, objects))
        print
        print Counter({type(obj): sys.getsizeof(obj) for obj in objects})

if __name__ == "__main__":
    main()
