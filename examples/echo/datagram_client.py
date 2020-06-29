from argparse import ArgumentParser
import errno
import re
import socket

import pymaid
from pymaid.channel import Channel


req = b'1234567890' * 100 + b'\n'
req_size = len(req)
channel = Channel()


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


class Echo(pymaid.protocols.BaseProtocol):

    def init(self):
        self.nbytes = 0

    def datagram_received(self, data, addr):
        self.nbytes += len(data)
        self.receive_event.set_result(data)

    def error_received(self, exc):
        self.transport.close()


async def wrapper(loop, address, count):
    while 1:
        try:
            if isinstance(address, str):
                raise ValueError(
                    'does not support unix domain socket with datagram'
                )
                # transport, protocol = await pymaid.create_unix_datagram(
                #     Echo, address
                # )
            else:
                transport, protocol = await pymaid.create_datagram(
                    Echo, address
                )
        except (socket.error, OSError) as ex:
            if ex.errno in {errno.EAGAIN, errno.ENOTCONN}:
                continue
            raise
        else:
            break

    write = transport.sendto
    for x in range(count):
        write(req)
        protocol.receive_event = loop.create_future()
        resp = await protocol.receive_event
        assert len(resp) == req_size, (len(resp), req_size)
    transport.close()
    assert protocol.nbytes == count * req_size, \
        (protocol.nbytes, count * req_size)


async def main(args):
    loop = pymaid.get_event_loop()
    tasks = []
    for x in range(args.concurrency):
        tasks.append(pymaid.create_task(
            wrapper(loop, args.address, args.request)
        ))

    await pymaid.wait(tasks)


if __name__ == "__main__":
    args = parse_args()
    if args.uvloop:
        import uvloop
        uvloop.install()
    pymaid.run(main(args))
