from pymaid.channel import Channel
from hello_pb2 import HelloResponse
from hello_pb2 import HelloService


class HelloServiceImpl(HelloService):

    def Hello(self, controller, request, done):
        response = HelloResponse()
        response.message = "from pymaid"
        done(response)

def main():
    channel = Channel()
    channel.listen("127.0.0.1", 8888)
    channel.append_service(HelloServiceImpl())
    channel.serve_forever()

if __name__ == "__main__":
    main()
