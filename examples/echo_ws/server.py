from __future__ import print_function

from pymaid.websocket.channel import WSChannel
from pymaid.utils import greenlet_pool

from echo_pb2 import Message, EchoService


class EchoServiceImpl(EchoService):

    def echo(self, controller, request, callback):
        response = Message()
        response.CopyFrom(request)
        callback(response)


def main():
    import gc
    from collections import Counter
    gc.set_debug(gc.DEBUG_LEAK&gc.DEBUG_UNCOLLECTABLE)
    gc.enable()

    channel = WSChannel(("", 8888))
    impl = EchoServiceImpl()
    channel.append_service(impl)
    try:
        channel.serve_forever()
    except:
        import traceback
        traceback.print_exc()
        print(len(channel.connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))

        objects = gc.get_objects()
        print(Counter(map(type, objects)))
        print()

if __name__ == "__main__":
    main()
