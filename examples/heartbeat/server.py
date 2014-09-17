import gevent
from pymaid.channel import Channel
from heartbeat_pb2 import Response
from heartbeat_pb2 import LongPlaying


class LongPlayingImpl(LongPlaying):

    def over_two_seconds(self, controller, request, done):
        gevent.sleep(2)
        response = Response()
        done(response)

def main():
    channel = Channel()
    channel.listen("127.0.0.1", 8888)
    channel.append_service(LongPlayingImpl())
    channel.enable_heartbeat(1, 3)
    channel.serve_forever()

if __name__ == "__main__":
    main()
