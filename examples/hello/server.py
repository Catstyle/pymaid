from __future__ import print_function

import pymaid
from pymaid.channel import Channel


class Channel(Channel):

    def connection_handler(self, conn):
        read, write = conn.readline, conn.write
        while 1:
            data = read(1024)
            if not data:
                break
            write(data)


def main():
    import gc
    from collections import Counter
    gc.set_debug(gc.DEBUG_LEAK&gc.DEBUG_UNCOLLECTABLE)
    gc.enable()

    channel = Channel()
    channel.listen('/tmp/hello.sock')
    channel.start()
    try:
        pymaid.serve_forever()
    except:
        print(len(channel.outgoing_connections))
        print(len(channel.incoming_connections))

        objects = gc.get_objects()
        print(Counter(map(type, objects)))

if __name__ == "__main__":
    main()
