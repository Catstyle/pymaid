import pymaid.rpc.pb

from examples.template import get_client_parser, parse_args


async def wrapper(address):
    conn = await pymaid.rpc.pb.dial_stream(address)
    # will be closed by server due to heartbeat timeout
    await conn.wait_for_closed()


async def main():
    args = parse_args(get_client_parser())
    tasks = []
    for x in range(args.concurrency):
        tasks.append(pymaid.create_task(wrapper(args.address)))

    # await pymaid.wait(tasks, timeout=args.timeout)
    await pymaid.gather(*tasks)


if __name__ == '__main__':
    pymaid.run(main())
