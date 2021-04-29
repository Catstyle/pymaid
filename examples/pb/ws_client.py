import pymaid
import pymaid.rpc.pb

from pymaid.net.ws import WebSocket
from pymaid.rpc.connection import Connection

from examples.template import get_client_parser, parse_args
from examples.pb.stub import worker

from echo_pb2 import EchoService_Stub


async def main(args):
    service = pymaid.rpc.pb.router.PBRouterStub(EchoService_Stub)
    tasks = []
    address = args.address
    request = args.request
    for x in range(args.concurrency):
        tasks.append(
            pymaid.create_task(
                worker(
                    address,
                    service,
                    request,
                    transport_class=WebSocket | Connection,
                )
            )
        )

    # await pymaid.wait(tasks, timeout=args.timeout)
    await pymaid.gather(*tasks)


if __name__ == "__main__":
    args = parse_args(get_client_parser())
    pymaid.run(main(args))
