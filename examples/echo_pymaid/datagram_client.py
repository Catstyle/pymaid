import pymaid

from examples.template import get_client_parser, parse_args


class Echo(pymaid.net.datagram.Datagram):

    def init(self):
        self.nbytes = 0
        self.receive_event = pymaid.Event()

    def datagram_received(self, data, addr):
        self.nbytes += len(data)
        self.receive_event.set()

    def error_received(self, exc):
        self.transport.close()


async def wrapper(loop, address, count):
    if isinstance(address, str):
        raise ValueError(
            'does not support unix domain socket with datagram'
        )
        # transport, protocol = await pymaid.create_unix_datagram(Echo, addres)
    else:
        transport, protocol = await pymaid.create_datagram(Echo, address)

    write = transport.sendto
    req = b'a' * args.msize
    receive_event = protocol.receive_event = pymaid.Event()
    for x in range(count):
        write(req)
        await receive_event.wait()
        receive_event.clear()
    transport.close()
    assert protocol.nbytes == count * args.msize, \
        (protocol.nbytes, count * args.msize)


async def main(args):
    loop = pymaid.get_event_loop()
    tasks = []
    for x in range(args.concurrency):
        tasks.append(pymaid.create_task(
            wrapper(loop, args.address, args.request)
        ))

    await pymaid.gather(*tasks)


if __name__ == "__main__":
    args = parse_args(get_client_parser())
    pymaid.run(main(args))
