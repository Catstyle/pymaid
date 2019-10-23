from __future__ import print_function
from argparse import ArgumentParser
import asyncio
import re


req = b'1234567890' * 100 + b'\n'
req_size = len(req)


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        '-c', dest='concurrency', type=int, default=100, help='concurrency'
    )
    parser.add_argument(
        '-r', dest='request', type=int, default=100, help='request per client'
    )
    parser.add_argument(
        '--address', type=str, default='/tmp/pymaid_hello.sock',
        help='connect address'
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


async def wrapper(address, count):
    if isinstance(address, str):
        reader, writer = await asyncio.open_unix_connection(address)
    else:
        reader, writer = await asyncio.open_connection(*address)
    asyncio.log.logger.debug(
        f'[conn][reader|{reader}][writer|{writer}] connected'
    )
    read, write = reader.read, writer.write
    for x in range(count):
        write(req)
        resp = await read(req_size)
        assert resp == req, len(resp)
    await writer.drain()
    writer.close()
    await writer.wait_closed()
    asyncio.log.logger.debug(
        f'[conn][reader|{reader}][writer|{writer}] closed'
    )


async def main(args):
    tasks = []
    for x in range(args.concurrency):
        tasks.append(asyncio.create_task(wrapper(args.address, args.request)))

    await asyncio.wait(tasks)


if __name__ == "__main__":
    args = parse_args()
    if args.uvloop:
        import uvloop
        uvloop.install()
    asyncio.run(main(args))
