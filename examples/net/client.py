import pymaid
from pymaid.net.stream import Stream

from examples.template import get_client_parser, parse_args


class Stream(Stream):

    def data_received(self, data):
        self.data_size += len(data)


def init(stream):
    stream.data_size = 0


async def wrapper(ch, count):
    stream = await ch.acquire(on_open=[init])

    for _ in range(count):
        await stream.write(b'a' * 8000)
    stream.shutdown()
    await stream.closed_event.wait()
    assert stream.data_size == 8000 * count, (stream.data_size, 8000 * count)


async def main(args):
    ch = await pymaid.net.dial_stream(args.address, transport_class=Stream)
    tasks = []
    for x in range(args.concurrency):
        tasks.append(pymaid.create_task(wrapper(ch, args.request)))

    # await pymaid.wait(tasks, timeout=args.timeout)
    await pymaid.gather(*tasks)


if __name__ == "__main__":
    args = parse_args(get_client_parser())
    pymaid.run(main(args))
