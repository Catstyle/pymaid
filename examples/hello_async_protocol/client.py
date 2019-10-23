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


class EchoProtocol(asyncio.Protocol):

    def __init__(self):
        self.nbytes = 0

    def connection_made(self, transport):
        socket = transport.get_extra_info('socket')
        print('Connection to {}'.format(socket))
        self.transport = transport

    def data_received(self, data):
        self.nbytes += len(data)
        self.receive_event.set_result(len(data))

    def eof_received(self):
        self.transport.close()

    def connection_lost(self, exc):
        print('Close the socket', exc)


async def wrapper(loop, address, count):
    if isinstance(address, str):
        transport, protocol = await loop.create_unix_connection(
            lambda: EchoProtocol(), address
        )
    else:
        transport, protocol = await asyncio.create_connection(
            lambda: EchoProtocol(), *address
        )
    write = transport.write
    for x in range(count):
        write(req)
        protocol.receive_event = loop.create_future()
        resp = await protocol.receive_event
        assert resp == req_size, (resp, req_size)
    transport.write_eof()
    assert protocol.nbytes == count * req_size, \
        (protocol.nbytes, count * req_size)


async def main(args):
    loop = asyncio.get_running_loop()
    tasks = []
    for x in range(args.concurrency):
        tasks.append(asyncio.create_task(
            wrapper(loop, args.address, args.request)
        ))

    await asyncio.wait(tasks)


if __name__ == "__main__":
    args = parse_args()
    if args.uvloop:
        import uvloop
        uvloop.install()
    asyncio.run(main(args))
