import pymaid
import pymaid.rpc.pb

from examples.template import get_client_parser, parse_args


async def wrapper(client, address, sleep_time):
    while 1:
        try:
            await client.connect(address)
        except BlockingIOError:
            await pymaid.sleep(0)
        else:
            break
    await pymaid.sleep(sleep_time)


async def main(args):
    if isinstance(args.address, str):
        client = pymaid.rpc.pb.channel.UnixStreamChannel()
    else:
        client = pymaid.rpc.pb.channel.StreamChannel()
    tasks = []
    for x in range(args.concurrency):
        tasks.append(pymaid.create_task(
            wrapper(client, args.address, args.sleep_time)
        ))

    # await pymaid.wait(tasks, timeout=args.timeout)
    await pymaid.gather(*tasks)


if __name__ == '__main__':
    parser = get_client_parser()
    parser.add_argument(
        'sleep_time', type=int, default=10, help='heartbeat timeout in seconds'
    )
    args = parse_args(parser)
    pymaid.run(main(args))
