import asyncio
import socket

from examples.template import get_client_parser, parse_args


async def wrapper(address, count):
    if isinstance(address, str):
        reader, writer = await asyncio.open_unix_connection(address)
    else:
        reader, writer = await asyncio.open_connection(*address)
    sock = writer.get_extra_info('socket')
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except (OSError, NameError):
        args.debug('set nodelay failed')
        pass
    args.debug(f'[conn][reader|{reader}][writer|{writer}] connected')

    req = b'a' * args.msize

    total = 0
    read, write = reader.read, writer.write
    for x in range(count):
        write(req)
        resp = await read(256 * 1024)
        total = len(resp)
    await writer.drain()
    writer.close()
    await writer.wait_for_closed()
    assert total == args.msize * count
    args.debug(f'[conn][reader|{reader}][writer|{writer}] closed')


async def main():
    global args
    args = parse_args(get_client_parser())
    tasks = []
    for x in range(args.concurrency):
        tasks.append(asyncio.create_task(wrapper(args.address, args.request)))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
