import pymaid
import pymaid.rpc.pb

from examples.template import get_client_parser, parse_args
from examples.pb.stub import worker

from echo_pb2 import EchoService_Stub


async def main():
    args = parse_args(get_client_parser())
    service = pymaid.rpc.pb.router.PBRouterStub(EchoService_Stub)
    address = args.address
    request = args.request
    tasks = [
        pymaid.create_task(worker(address, service, request))
        for _ in range(args.concurrency)
    ]

    # await pymaid.wait(tasks, timeout=args.timeout)
    await pymaid.gather(*tasks)


if __name__ == "__main__":
    pymaid.run(main())
