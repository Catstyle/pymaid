from __future__ import print_function

from pymaid import serve_forever
from pymaid.channel import ServerChannel
from pymaid.parser import PBParser
from pymaid.pb import Listener, PBHandler
from pymaid.utils import greenlet_pool

from pymaid.apps.monitor.service import MonitorServiceImpl
from pymaid.apps.monitor.middleware import MonitorMiddleware


def main():
    listener = Listener()
    listener.append_service(MonitorServiceImpl())
    channel = ServerChannel(PBHandler, listener, parser=PBParser)
    #channel.listen(('localhost', 8888))
    channel.listen('/tmp/hello_pb.sock')
    channel.append_middleware(MonitorMiddleware(1, 3))
    channel.start()
    try:
        serve_forever()
    except:
        print(len(channel.connections))
        print(greenlet_pool.size, len(greenlet_pool.greenlets))


if __name__ == "__main__":
    main()
