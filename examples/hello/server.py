from gevent import wait

from pymaid.channel import Channel
from hello_pb2 import HelloResponse
from hello_pb2 import HelloService


class HeeloServiceImpl(HelloService):

    def Hello(self, controller, request, done):
        response = HelloResponse()
        response.message = "from pymaid"
        return response

def main():
    channel = Channel()
    channel.listen("127.0.0.1", 8888)
    channel.append_service(HeeloServiceImpl())
    wait()

if __name__ == "__main__":
    main()
