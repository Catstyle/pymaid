import pymaid
import pymaid.net.ws

from examples.template import get_server_parser, parse_args


class EchoStream(pymaid.net.ws.WebSocket):

    KEEP_OPEN_ON_EOF = False

    def data_received(self, data: bytes):
        self.write_sync(data)


async def main():
    args = parse_args(get_server_parser())
    ch = await pymaid.net.serve_stream(
        args.address, transport_class=EchoStream
    )
    async with ch:
        await ch.serve_forever()


if __name__ == "__main__":
    pymaid.run(main())
