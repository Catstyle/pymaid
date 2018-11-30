from __future__ import print_function
import re
from argparse import ArgumentParser

import pymaid
from pymaid.channel import ServerChannel


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '--address', type=str, default='/tmp/pymaid_hello.sock',
        help='listen address'
    )

    args = parser.parse_args()
    if re.search(r':\d+$', args.address):
        address, port = args.address.split(':')
        args.address = (address, int(port))
    print(args)
    return args


def handler(conn):
    readline, write = conn.readline, conn.write
    while 1:
        data = readline(1024)
        if not data:
            break
        write(data)
    conn.close()


def main(args):
    channel = ServerChannel(handler)
    channel.listen(args.address)
    channel.start()
    try:
        pymaid.serve_forever()
    except:
        print(len(channel.connections))


if __name__ == "__main__":
    args = parse_args()
    main(args)
