import pymaid

from examples.template import get_server_parser, parse_args
from examples.pb.service import EchoImpl


async def main(args):
    ch = await pymaid.rpc.pb.serve_stream(args.address, services=[EchoImpl()])
    async with ch:
        await ch.serve_forever()


if __name__ == "__main__":
    args = parse_args(get_server_parser())
    pymaid.run(main(args))
