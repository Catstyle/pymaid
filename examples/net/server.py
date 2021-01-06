import pymaid
from pymaid.net.stream import Stream

from examples.template import get_server_parser, parse_args


class Stream(Stream):

    def data_received(self, data):
        # cannot use asynchronous way since this is in io callback
        self.write_sync(data)


async def main(args):
    ch = await pymaid.net.serve_stream(args.address, stream_class=Stream)
    async with ch:
        await ch.serve_forever()


if __name__ == "__main__":
    args = parse_args(get_server_parser())
    pymaid.run(main(args))
