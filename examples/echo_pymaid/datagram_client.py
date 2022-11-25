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
    for _ in range(count):
        write(req)
        await receive_event.wait()
        receive_event.clear()
    transport.close()
    assert protocol.nbytes == count * args.msize, \
        (protocol.nbytes, count * args.msize)


async def main():
    global args
    args = parse_args(get_client_parser())
    loop = pymaid.get_event_loop()
    tasks = [pymaid.create_task(
            wrapper(loop, args.address, args.request)
        ) for _ in range(args.concurrency)]
    await pymaid.gather(*tasks)


if __name__ == "__main__":
    pymaid.run(main())
