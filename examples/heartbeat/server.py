import pymaid
import pymaid.rpc.pb

from pymaid.ext.middleware import MiddlewareManager
from pymaid.ext.monitor import HeartbeatMiddleware

from examples.template import get_server_parser, parse_args


async def main(args):
    mm = MiddlewareManager([HeartbeatMiddleware(args.interval, args.retry)])
    await pymaid.rpc.pb.serve_stream(
        args.address, backlog=args.backlog, services=[], middleware_manager=mm
    )


if __name__ == "__main__":
    parser = get_server_parser()
    parser.add_argument(
        'interval', type=int, default=10, help='heartbeat timeout in seconds'
    )
    parser.add_argument(
        'retry', type=int, default=3, help='retry before heartbeat timeout'
    )
    args = parse_args(parser)
    pymaid.run(main(args))
