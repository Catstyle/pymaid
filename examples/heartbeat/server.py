import pymaid
import pymaid.rpc.pb

from pymaid.ext.middleware import MiddlewareManager
from pymaid.ext.monitor import HeartbeatMiddleware

from examples.template import get_server_parser, parse_args


async def main():
    parser = get_server_parser()
    parser.add_argument(
        'interval', type=int, default=10, help='heartbeat timeout in seconds'
    )
    parser.add_argument(
        'retry', type=int, default=3, help='retry before heartbeat timeout'
    )
    args = parse_args(parser)

    mm = MiddlewareManager([HeartbeatMiddleware(args.interval, args.retry)])
    ch = await pymaid.rpc.pb.serve_stream(
        args.address, backlog=args.backlog, services=[], middleware_manager=mm
    )
    async with ch:
        await ch.serve_forever()


if __name__ == "__main__":
    pymaid.run(main())
