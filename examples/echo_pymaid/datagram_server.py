import pymaid

from examples.template import get_server_parser, parse_args


class Echo(pymaid.net.datagram.Datagram):

    def datagram_received(self, data: bytes, addr):
        self.transport.sendto(data, addr)

    def error_received(self, exc):
        self.transport.close()


async def main():
    args = parse_args(get_server_parser())
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


if __name__ == "__main__":
    pymaid.run(main())
