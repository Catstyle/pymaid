from pymaid.channel import Channel
from pymaid.service_proxy import ServiceProxy
from hello_pb2 import HelloService_Stub

def main():
    channel = Channel()
    service = ServiceProxy(HelloService_Stub(channel))
    conn = channel.connect("127.0.0.1", 8888)
    #controller.conn = conn
    for x in xrange(2000):
        response = service.Hello()
        assert response.message == 'from pymaid', response.message
        #controller.Reset()
    conn.close()

    for x in xrange(1000):
        conn = channel.connect("127.0.0.1", 8888)
        #controller = Controller()
        #controller.conn = conn
        response = service.Hello()
        assert response.message == 'from pymaid', response.message
        conn.close()
    assert len(channel._pending_results) == 0
    assert len(channel._connections) == 0

if __name__ == "__main__":
    main()
