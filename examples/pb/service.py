import pymaid
from pymaid.rpc.pb.context import InboundContext

# generated by protoc
from echo_pb2 import EchoService


@pymaid.rpc.pb.implall
class EchoImpl(EchoService):

    async def UnaryUnaryEcho(self, context: InboundContext):
        #  echo the same message
        await context.send_message(await context.recv_message())

    async def UnaryStreamEcho(self, context: InboundContext):
        request = await context.recv_message()
        await context.send_message(request)
        await context.send_message(request, end=True)
        # can be separated into steps, but will result in an extra message
        # await context.send_message(request)
        # await context.send_message(request)
        # await context.send_message(end=True)

    async def StreamUnaryEcho(self, context: InboundContext):
        async for req in context:
            # do something with request
            pass
        await context.send_message(req)

    async def StreamStreamEcho(self, context: InboundContext):
        async for req in context:
            await context.send_message(req)
        # you can send end message yourself
        # or let context handle this at cleanup for you
        # await context.send_message(end=True)
