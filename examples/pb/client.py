import pymaid
import pymaid.rpc.pb
# from pymaid.ext.pools.worker import AioPool

from examples.template import get_client_parser, parse_args

from echo_pb2 import EchoService_Stub, Message


async def wrapper(client, service, address, count):
    while 1:
        try:
            conn = await client.connect(address)
        except BlockingIOError:
            await pymaid.sleep(0)
        else:
            break
    request = Message(message='a' * 8000)

    def cb(resp):
        assert len(resp.message) == 8000

    # async with AioPool(size=10) as pool:
    for x in range(count):
        # await pool.spawn(service.UnaryUnaryEcho(request, conn=conn), callback=cb)
        resp = await service.UnaryUnaryEcho(request, conn=conn)
        assert len(resp.message) == 8000

        # # This block performs the same UNARY_UNARY interaction as above
        # # while showing more advanced stream control features.
        # async with service.UnaryUnaryEcho.open(conn=conn) as controller:
        #     controller.send_message(request)
        #     resp = await controller.recv_message()
        #     assert len(resp.message) == 8000

        # resp = await service.UnaryStreamEcho(request, conn=conn)
        # assert len(resp) == 5
        # assert all(len(r.message) == 8000 for r in resp)

        # # This block performs the same UNARY_STREAM interaction as above
        # # while showing more advanced stream control features.
        # async with await service.UnaryStreamEcho.open(conn=conn) as controller:
        #     await controller.send_message(request)
        #     resp = [r async for r in controller]
        #     assert len(resp) == 5
        #     assert all(len(r.message) == 8000 for r in resp)
    conn.shutdown()
    conn.close()


async def main(args):
    if isinstance(args.address, str):
        client = pymaid.rpc.pb.channel.UnixStreamChannel()
    else:
        client = pymaid.rpc.pb.channel.StreamChannel()
    service = pymaid.rpc.method.ServiceStub(EchoService_Stub)
    tasks = []
    for x in range(args.concurrency):
        tasks.append(pymaid.create_task(
            wrapper(client, service, args.address, args.request)
        ))

    # await pymaid.wait(tasks, timeout=args.timeout)
    await pymaid.gather(*tasks)


if __name__ == "__main__":
    args = parse_args(get_client_parser())
    pymaid.run(main(args))
