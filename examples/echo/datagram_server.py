from argparse import ArgumentParser
import re

import pymaid


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


class Echo(pymaid.protocols.BaseProtocol):

    def datagram_received(self, data: bytes, addr):
        self.transport.sendto(data, addr)

    def error_received(self, exc):
        self.transport.close()


async def main(args):
    if isinstance(args.address, str) and args.uvloop:
        raise ValueError('does not support unix domain socket with datagram')
        # transport, protocol = await pymaid.create_unix_datagram_server(
        #     Echo, args.address
        # )
    else:
        transport, protocol = await pymaid.create_datagram_server(
            Echo, args.address
        )
    while 1:
        await pymaid.sleep(3)
        print(protocol.counter)


if __name__ == "__main__":
    args = parse_args()
    if args.uvloop:
        import uvloop
        uvloop.install()
    pymaid.run(main(args))
