import asyncio

from examples.template import get_client_parser, parse_args


class EchoProtocol(asyncio.Protocol):

    def __init__(self):
        self.nbytes = 0

    def connection_made(self, transport):
        sock = transport.get_extra_info('socket')
        args.debug(f'Connection to {sock}')
        self.transport = transport

    def data_received(self, data):
        self.nbytes += len(data)
        self.receive_event.set()

    def eof_received(self):
        self.transport.close()

    def connection_lost(self, exc):
        args.debug('Close the socket', self.transport, exc)
        self.transport = None


async def wrapper(loop, address, count):
    if isinstance(address, str):
        transport, protocol = await loop.create_unix_connection(
            EchoProtocol, address
        )
    else:
        transport, protocol = await asyncio.create_connection(
            EchoProtocol, *address
        )

    write = transport.write
    req = b'a' * args.msize
    receive_event = protocol.receive_event = asyncio.Event()
    for _ in range(count):
        write(req)
        await receive_event.wait()
        receive_event.clear()
    transport.write_eof()
    transport.close()
    assert protocol.nbytes == count * args.msize, \
        (protocol.nbytes, count * args.msize)


async def main():
    global args
    args = parse_args(get_client_parser())
    loop = asyncio.get_running_loop()
    tasks = [asyncio.create_task(
            wrapper(loop, args.address, args.request)
        ) for _ in range(args.concurrency)]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
