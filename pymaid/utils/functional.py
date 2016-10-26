from .logger import logger_wrapper

__all__ = ['ObjectManager']


@logger_wrapper
class ObjectManager():

    def __init__(self, name):
        self.name = name
        self.objects = {}

    def add(self, pk, obj):
        self.logger.info('[%s][add|%r][%s]', self.name, pk, obj)
        assert pk not in self.objects, pk
        self.objects[pk] = obj
        obj._manager = self

    def has(self, pk):
        return pk in self.objects

    def get(self, pk):
        assert pk in self.objects
        return self.objects[pk]

    def remove(self, pk):
        self.logger.info('[%s][remove|%r]', self.name, pk)
        assert pk in self.objects
        obj = self.objects.pop(pk)
        obj._manager = None
        return obj


def get_ipaddress(ifname):
    import socket
    import struct
    import fcntl
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(
        fcntl.ioctl(
            s.fileno(), 0x8915, struct.pack('256s', ifname[:15])
        )[20:24]
    )
