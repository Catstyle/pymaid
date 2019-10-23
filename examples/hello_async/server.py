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


async def handler(reader, writer):
    asyncio.log.logger.debug(
        f'[conn][reader|{reader}][writer|{writer}] connected'
    )
    read, write = reader.read, writer.write
    while 1:
        data = await read(1024)
        if not data:
            break
        write(data)
    await writer.drain()
    writer.close()
    await writer.wait_closed()
    asyncio.log.logger.debug(
        f'[conn][reader|{reader}][writer|{writer}] closed'
    )


async def main(args):
    if isinstance(args.address, str):
        channel = await asyncio.start_unix_server(handler, args.address)
    else:
        channel = await asyncio.start_server(handler, *args.address)

    async with channel:
        await channel.serve_forever()


if __name__ == "__main__":
    args = parse_args()
    if args.uvloop:
        import uvloop
        uvloop.install()
    asyncio.run(main(args))
