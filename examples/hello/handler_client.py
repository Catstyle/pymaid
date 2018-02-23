from __future__ import print_function

import pymaid
from pymaid.channel import ClientChannel
from pymaid.hub import greenlet_pool


req = '1234567890' * 100 + '\n'
req_size = len(req)


def handler(conn):
    read, write = conn.readline, conn.write
    for x in range(10000):
        write(req)
        resp = read(req_size)
        assert resp == req, len(resp)
    conn.close()


handler_channel = ClientChannel(handler)


def main():
    for x in range(100):
        # handler run on an independent greenlet
        handler_channel.connect('/tmp/hello.sock')

    try:
        pymaid.serve_forever()
    except Exception:
        import traceback
        traceback.print_exc()
        print(len(handler_channel.connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    main()
