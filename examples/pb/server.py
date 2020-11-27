import pymaid
import pymaid.rpc.pb

from examples.template import get_server_parser, parse_args

from echo_pb2 import EchoService, Message


@pymaid.rpc.utils.implall
class EchoImpl(EchoService):

    async def UnaryUnaryEcho(
        self,
        controller: pymaid.rpc.pb.controller.Controller,
        request: Message,
    ):
        controller.send_message(request)

    async def UnaryStreamEcho(self, controller, request: Message):
        for _ in range(4):
            controller.send_message(request)
        controller.send_message(request, end=True)

        # act the same as above, but call controller.end explicitly
        # this will result in an extra message
        # for _ in range(5):
        #     await controller.send_message(message)
        # await controller.end()

    async def StreamUnaryEcho(self, controller, requests):
        messages = [m async for m in requests]
        controller.send_message(messages[0])

    async def StreamStreamEcho(self, controller, requests):
        async for message in requests:
            controller.send_message(message)
        controller.send_message(end=True)


async def main(args):
    if isinstance(args.address, str):
        server = pymaid.rpc.pb.channel.UnixStreamChannel([EchoImpl()])
    else:
        server = pymaid.rpc.pb.channel.StreamChannel([EchoImpl()])
    await server.listen(args.address)
    await server.start()
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    args = parse_args(get_server_parser())
    pymaid.run(main(args))
