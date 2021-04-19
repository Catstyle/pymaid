import pymaid
import pymaid.net.ws

from examples.template import get_client_parser, parse_args


class EchoStream(pymaid.net.ws.WebSocket):

    KEEP_OPEN_ON_EOF = False

    # the same as the init function below
    # def init(self):
    #     self.data_size = 0

    def data_received(self, data):
        self.data_size += len(data)


# the same as the init method above
def init(stream):
    stream.data_size = 0


async def wrapper(ch, count):
    stream = await ch.acquire(on_open=[init])

    for _ in range(count):
        # NOTE: websocket should use `send` instead of `write`
        await stream.send(b'a' * 8000)
    stream.shutdown()
    await stream.wait_closed()
    assert stream.data_size == 8000 * count, (stream.data_size, 8000 * count)


async def main(args):
    ch = await pymaid.net.dial_stream(args.address, transport_class=EchoStream)
    tasks = []
    for x in range(args.concurrency):
        tasks.append(pymaid.create_task(wrapper(ch, args.request)))

    # await pymaid.wait(tasks, timeout=args.timeout)
    await pymaid.gather(*tasks)


if __name__ == "__main__":
    args = parse_args(get_client_parser())
    pymaid.run(main(args))
