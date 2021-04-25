import pymaid
import pymaid.rpc.pb

from examples.template import get_client_parser, parse_args

from echo_pb2 import EchoService_Stub, Message

request = Message(message='a' * 8000)


async def get_requests():
    yield request
    yield request


async def wrapper(address, service, count):
    conn = await pymaid.rpc.pb.dial_stream(address)

    for x in range(count):
        # UnaryUnaryEcho
        resp = await service.UnaryUnaryEcho(request, conn=conn)
        assert len(resp.message) == 8000

        # # This block performs the same UNARY_UNARY interaction as above
        # # while showing more advanced stream control features.
        # async with service.UnaryUnaryEcho.open(conn=conn) as context:
        #     await context.send_message(request)
        #     resp = await context.recv_message()
        #     assert len(resp.message) == 8000

        # UnaryStreamEcho
        async for resp in service.UnaryStreamEcho(request, conn=conn):
            assert len(resp.message) == 8000

        # # This block performs the same UNARY_STREAM interaction as above
        # # while showing more advanced stream control features.
        # async with service.UnaryStreamEcho.open(conn=conn) as context:
        #     await context.send_message(request)
        #     async for resp in context:
        #         assert len(resp.message) == 8000

        # StreamUnaryEcho
        resp = await service.StreamUnaryEcho(get_requests(), conn=conn)
        assert len(resp.message) == 8000

        # # This block performs the same STREAM_UNARY interaction as above
        # # while showing more advanced stream control features.
        # async with service.StreamUnaryEcho.open(conn=conn) as context:
        #     async for req in get_requests():
        #         await context.send_message(req)
        #         # you can still do something here
        #     # CAUTION, DO NOT FORGET TO SEND THE END MESSAGE
        #     await context.send_message(end=True)
        #     resp = await context.recv_message()
        #     assert len(resp.message) == 8000

        # StreamStreamEcho
        async for resp in service.StreamStreamEcho(get_requests(), conn=conn):
            assert len(resp.message) == 8000

        # # This block performs the same STREAM_STREAM interaction as above
        # # while showing more advanced stream control features.
        # async with service.StreamStreamEcho.open(conn=conn) as context:
        #     async for req in get_requests():
        #         await context.send_message(request)
        #         # you can still do something here
        #         resp = await context.recv_message()
        #         assert len(resp.message) == 8000
        #     # or you can send requests first, then wait for responses
        #     async for req in get_requests():
        #         await context.send_message(request)
        #         # you can still do something here
        #     async for resp in context:
        #         # you can still do something here
        #         assert len(resp.message) == 8000
        #     # you can send end message yourself
        #     # or let context handle this at cleanup for you
        #     await context.send_message(end=True)
    conn.shutdown()
    conn.close()
    await conn.wait_closed()


async def main(args):
    service = pymaid.rpc.pb.router.PBRouterStub(EchoService_Stub)
    tasks = []
    for x in range(args.concurrency):
        tasks.append(
            pymaid.create_task(wrapper(args.address, service, args.request))
        )

    # await pymaid.wait(tasks, timeout=args.timeout)
    await pymaid.gather(*tasks)


if __name__ == "__main__":
    args = parse_args(get_client_parser())
    pymaid.run(main(args))
