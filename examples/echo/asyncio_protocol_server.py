from __future__ import print_function
from argparse import ArgumentParser
import asyncio
import re


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '--address', type=str, default='/tmp/pymaid_hello.sock',
        help='listen address'
    )
    parser.add_argument(
        '--uvloop', action='store_true', default=False, help='use uvloop'
    )

    args = parser.parse_args()
    if re.search(r':\d+$', args.address):
        address, port = args.address.split(':')
        args.address = (address, int(port))
    print(args)
    return args


class EchoProtocol(asyncio.Protocol):

    def connection_made(self, transport):
        sock = transport.get_extra_info('socket')
        print('Connection from {}'.format(sock))
        self.transport = transport

    def data_received(self, data):
        self.transport.write(data)

    def eof_received(self):
        self.transport.close()

    def connection_lost(self, exc):
        print('Close the socket', self.transport, exc)


async def main(args):
    loop = asyncio.get_running_loop()
    if isinstance(args.address, str):
        channel = await loop.create_unix_server(EchoProtocol, args.address)
    else:
        channel = await loop.create_server(EchoProtocol, *args.address)

    async with channel:
        await channel.serve_forever()


if __name__ == "__main__":
    args = parse_args()
    if args.uvloop:
        import uvloop
        uvloop.install()
    asyncio.run(main(args))
