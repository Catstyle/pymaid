import pymaid

from echo_pb2 import Message

request = Message(message='a' * 8000)


async def get_requests():
    yield request
    yield request


async def worker(address, service, count, **kwargs):
    conn = await pymaid.rpc.pb.dial_stream(address, **kwargs)

    for _ in range(count):
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

    conn.shutdown()
    conn.close()
    await conn.wait_closed()
