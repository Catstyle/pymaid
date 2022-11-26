import asyncio
import socket

from examples.template import get_server_parser, parse_args


async def handler(reader, writer):
    args.debug(f'[conn][reader|{reader}][writer|{writer}] connected')
    sock = writer.get_extra_info('socket')
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except (OSError, NameError) as ex:
        args.debug(f'set nodelay failed {ex}')
        pass
    read, write = reader.read, writer.write
    while 1:
        data = await read(256 * 1024)
        if not data:
            break
        write(data)
    await writer.drain()
    writer.close()
    await writer.wait_for_closed()
    args.debug(f'[conn][reader|{reader}][writer|{writer}] closed')


async def main():
    global args
    args = parse_args(get_server_parser())
    if isinstance(args.address, str):
        channel = await asyncio.start_unix_server(handler, args.address)
    else:
        channel = await asyncio.start_server(handler, *args.address)

    async with channel:
        await channel.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
