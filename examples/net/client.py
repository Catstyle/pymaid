import pymaid
from pymaid.net.stream import Stream

from examples.template import get_client_parser, parse_args


class Stream(Stream):

    def init(self):
        self.data_size = 0

    def data_received(self, data):
        self.data_size += len(data)


async def wrapper(address, count):
    stream = await pymaid.net.dial_stream(address, transport_class=Stream)

    for _ in range(count):
        await stream.write(b'a' * 8000)
    stream.shutdown()
    await stream.wait_for_closed()
    assert stream.data_size == 8000 * count, (stream.data_size, 8000 * count)


async def main():
    args = parse_args(get_client_parser())
    tasks = []
    for x in range(args.concurrency):
        tasks.append(pymaid.create_task(wrapper(args.address, args.request)))

    # await pymaid.wait(tasks, timeout=args.timeout)
    await pymaid.gather(*tasks)


if __name__ == "__main__":
    pymaid.run(main())
