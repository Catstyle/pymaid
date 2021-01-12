import asyncio

from examples.template import get_server_parser, parse_args


class EchoProtocol(asyncio.Protocol):

    def connection_made(self, transport):
        sock = transport.get_extra_info('socket')
        args.debug('Connection from {}'.format(sock))
        self.transport = transport

    def data_received(self, data):
        self.transport.write(data)

    def eof_received(self):
        self.transport.close()

    def connection_lost(self, exc):
        args.debug('Close the socket', self.transport, exc)


async def main(args):
    loop = asyncio.get_running_loop()
    if isinstance(args.address, str):
        channel = await loop.create_unix_server(
            EchoProtocol, args.address, backlog=args.backlog,
        )
    else:
        channel = await loop.create_server(
            EchoProtocol, *args.address, backlog=args.backlog,
        )

    async with channel:
        await channel.serve_forever()


if __name__ == "__main__":
    args = parse_args(get_server_parser())
    asyncio.run(main(args))
