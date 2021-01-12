import pymaid

from examples.template import get_server_parser, parse_args


class EchoStream(pymaid.net.Stream):

    def data_received(self, data: bytes):
        self.write(data)

    def eof_received(self):
        # return value indicate keep_open
        return False


async def main(args):
    if isinstance(args.address, str):
        server = await pymaid.create_unix_stream_server(
            EchoStream, args.address
        )
    else:
        server = await pymaid.create_stream_server(EchoStream, *args.address)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    args = parse_args(get_server_parser())
    pymaid.run(main(args))
