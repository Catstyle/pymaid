import pymaid
import pymaid.net.ws

from examples.template import get_client_parser, parse_args


class EchoStream(pymaid.net.ws.WebSocket):

    KEEP_OPEN_ON_EOF = False

    # the same as the init function below
    def init(self):
        self.data_size = 0

    def data_received(self, data):
        self.data_size += len(data)


async def wrapper(address, count):
    stream = await pymaid.net.dial_stream(address, transport_class=EchoStream)

    for _ in range(count):
        await stream.write(b'a' * 8000)
    stream.shutdown()
    await stream.wait_closed()
    assert stream.data_size == 8000 * count, (stream.data_size, 8000 * count)


async def main(args):
    tasks = []
    for x in range(args.concurrency):
        tasks.append(pymaid.create_task(wrapper(args.address, args.request)))

    # await pymaid.wait(tasks, timeout=args.timeout)
    await pymaid.gather(*tasks)


if __name__ == "__main__":
    args = parse_args(get_client_parser())
    pymaid.run(main(args))
