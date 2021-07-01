import pymaid
from pymaid.net.ws import WebSocket
from pymaid.rpc.connection import Connection

from examples.template import get_server_parser, parse_args
from examples.pb.service import EchoImpl


async def main():
    args = parse_args(get_server_parser())
    ch = await pymaid.rpc.pb.serve_stream(
        args.address,
        transport_class=WebSocket | Connection,
        services=[EchoImpl()],
    )
    async with ch:
        await ch.serve_forever()


if __name__ == "__main__":
    pymaid.run(main())
