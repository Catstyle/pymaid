import pymaid
import pymaid.net.ws

from examples.template import get_client_parser, parse_args


req = b'1234567890' * 100 + b'\n'
req_size = len(req)


class EchoStream(pymaid.net.ws.WebSocket):

    def init(self):
        self.nbytes = 0

    def data_received(self, data):
        self.nbytes += len(data)
        self.receive_event.set_result(data)

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
    for x in range(count):
        write(req)
        transport.receive_event = loop.create_future()
        resp = await transport.receive_event
        assert len(resp) == req_size, (len(resp), req_size)
    transport.write_eof()
    transport.close()
    assert transport.nbytes == count * req_size, \
        (transport.nbytes, count * req_size)


async def main(args):
    loop = pymaid.get_event_loop()
    tasks = []
    for x in range(args.concurrency):
        tasks.append(pymaid.create_task(
            wrapper(loop, args.address, args.request)
        ))

    # await pymaid.wait(tasks, timeout=args.timeout)
    await pymaid.gather(*tasks)


if __name__ == "__main__":
    args = parse_args(get_client_parser())
    pymaid.run(main(args))
