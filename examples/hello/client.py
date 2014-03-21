from gprpc.channel import Channel
from gprpc.controller import Controller
from hello_pb2 import HelloService_Stub
from hello_pb2 import HelloRequest

def main():
    channel = Channel("127.0.0.1", 8888)
    stub = HelloService_Stub(channel)
    conn = channel.new_connection()
    controller = Controller()
    controller.conn = conn
    request = HelloRequest()
    for x in xrange(2000):
        response = stub.Hello(controller, request, None).get()
        assert response.message == 'from pymaid', response.message
        controller.Reset()
    conn.close()

    #for x in xrange(1000):
    #    conn = channel.new_connection()
    #    controller = Controller()
    #    controller.conn = conn
    #    response = stub.Hello(controller, request, None).get()
    #    assert response.message == 'from pymaid', response.message
    #    conn.close()
    assert len(channel._pending_request) == 0
    assert len(channel._connections) == 0

if __name__ == "__main__":
    main()
