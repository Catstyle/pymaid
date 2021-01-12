import pymaid

from examples.template import get_client_parser, parse_args


class EchoStream(pymaid.net.Stream):

    def init(self):
        self.nbytes = 0
        self.receive_event = pymaid.Event()

    def data_received(self, data):
        self.nbytes += len(data)
        self.receive_event.set()

    def eof_received(self):
        # return value indicate keep_open
        return False


async def wrapper(loop, address, count):
    if isinstance(address, str):
        transport = await pymaid.create_unix_stream(EchoStream, address)
    else:
        transport = await pymaid.create_stream(EchoStream, *address)

    # in this example, only use transport
    write = transport.write
    req = b'a' * args.msize
    receive_event = transport.protocol.receive_event
    for x in range(count):
        write(req)
        await receive_event.wait()
        receive_event.clear()
    transport.write_eof()
    transport.close()
    assert transport.nbytes == count * args.msize, \
        (transport.nbytes, count * args.msize)


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
