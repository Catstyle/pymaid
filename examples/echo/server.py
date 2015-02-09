from pymaid.channel import Channel
from pymaid.connection import Connection
from pymaid.utils import greenlet_pool

from echo_pb2 import Message
from echo_pb2 import EchoService

Connection.MAX_PACKET_LENGTH = 10000000


class EchoServiceImpl(EchoService):

    def echo(self, controller, request, callback):
        response = Message()
        response.message = request.message
        callback(response)

def main():
    import gc
    from collections import Counter
    gc.set_debug(gc.DEBUG_LEAK&gc.DEBUG_UNCOLLECTABLE)
    gc.enable()

    channel = Channel()
    channel.listen("127.0.0.1", 8888)
    channel.append_service(EchoServiceImpl())
    #channel.enable_heartbeat(10, 3)
    try:
        channel.serve_forever()
    except:
        print len(channel._outcome_connections)
        print len(channel._income_connections)
        print greenlet_pool.size, len(greenlet_pool.greenlets)

        objects = gc.get_objects()
        print Counter(map(type, objects))
        print

if __name__ == "__main__":
    main()
