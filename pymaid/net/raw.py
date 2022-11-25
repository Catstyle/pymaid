'''Raw socket layer.

Mostly inspired from standard lib `asyncio`.
'''

import os
import re
import socket

from errno import ENOTCONN, ECONNABORTED
from typing import List

from pymaid.conf import settings
from pymaid.core import get_running_loop, run_in_threadpool, sleep

HAS_IPv6_FAMILY = hasattr(socket, 'AF_INET6')
HAS_IPv6_PROTOCOL = hasattr(socket, 'IPPROTO_IPV6')

HAS_UNIX_FAMILY = hasattr(socket, 'AF_UNIX')

STREAM_OPTS = {
    'tcp': (socket.AF_UNSPEC, socket.SOCK_STREAM),
    'tcp4': (socket.AF_INET, socket.SOCK_STREAM),
    'tcp6': (socket.AF_INET6, socket.SOCK_STREAM),
    'unix': (socket.AF_UNIX, socket.SOCK_STREAM),
}

DATAGRAM_OPTS = {
    'udp': (socket.AF_UNSPEC, socket.SOCK_DGRAM),
    'udp4': (socket.AF_INET, socket.SOCK_DGRAM),
    'udp6': (socket.AF_INET6, socket.SOCK_DGRAM),
    'unix': (socket.AF_UNIX, socket.SOCK_DGRAM),
}

NET_OPTS = {
    **STREAM_OPTS,
    **DATAGRAM_OPTS,
    'any': (socket.AF_UNSPEC, 0),
    'unix': (socket.AF_UNIX, 0),
}

ADDRESS_REGEX = re.compile(r'([\w\.]+):?(\w*)|\[([\w:]+)\]:?(\w*)')


async def getaddrinfo(
    address: str,
    family: socket.AddressFamily,
    socket_kind: socket.SocketKind,
    flags: int = 0,
):
    if address.startswith('/'):
        if family not in {socket.AF_UNIX, socket.AF_UNSPEC}:
            raise ValueError(
                'address starts with `/` should be unix family, '
                f'got address={address} family={family}'
            )
        if socket_kind == 0:
            infos = [
                (socket.AF_UNIX, socket.SOCK_STREAM, 0, '', address),
                (socket.AF_UNIX, socket.SOCK_DGRAM, 0, '', address),
            ]
        else:
            infos = [(socket.AF_UNIX, socket_kind, 0, '', address)]
    else:
        match = ADDRESS_REGEX.match(address)
        if not match:
            raise ValueError(f'invalid address: {address}')
        host, port = (g for g in match.groups() if g)
        infos = await run_in_threadpool(
            socket.getaddrinfo,
            args=(host, port, family, socket_kind),
            kwargs={'flags': flags},
        )
        infos = list(set(infos))
    return infos


def set_sock_options(sock: socket.socket):
    # stream opts
    if sock.type == socket.SOCK_STREAM and sock.family != socket.AF_UNIX:
        setsockopt = sock.setsockopt

        setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


async def sock_connect(
    net: str,
    address: str,
    flags: int = 0,
) -> socket.socket:
    loop = get_running_loop()
    err = None
    if net not in STREAM_OPTS:
        raise ValueError(f'only support {STREAM_OPTS.keys()} now, got {net}')
    family, socket_kind = STREAM_OPTS[net]
    addr_infos = await getaddrinfo(address, family, socket_kind, flags)
    for addr_info in addr_infos:
        retry = 3
        af, kind, proto, canonname, sa = addr_info
        sock = None
        while 1:
            try:
                sock = socket.socket(af, kind, proto)
                sock.setblocking(False)
                await loop.sock_connect(sock, sa)
                set_sock_options(sock)
                # NOTE:
                # When doing a lots connect to remote side under heavy pressure
                # it would sometimes getting ENOTCONN when call getpeername.
                # Check it here, if occured, raise it to retry.
                # *WHY* sock_connect above does not handle this case?
                # NOTE 2:
                # This case appears to inconsistently occur with
                # bound to a unix domain socket.
                sock.getpeername()
                # Break explicitly a reference cycle
                err = None
                return sock
            except socket.error as _:
                if _.errno == 107:
                    # OSError: [Errno 107] Transport endpoint is not connected
                    # special case when dealing with 107, it seems retry later
                    # is ok.
                    await sleep(0.001)
                    continue
                if _.errno in {ECONNABORTED, ENOTCONN} and retry:
                    retry -= 1
                    continue
                err = _
                if sock is not None:
                    sock.close()
                break

    if err is None:
        raise socket.error('getaddrinfo returns an empty list')
    try:
        raise err
    finally:
        # Break explicitly a reference cycle
        err = None


async def sock_listen(
    net: str,
    address: str,
    flags: socket.AddressInfo = socket.AI_PASSIVE,
    backlog: int = 4096,
    reuse_address: bool = True,
    reuse_port: bool = False,
) -> List[socket.socket]:
    '''Create sockets listening on `address`.

    The address parameter can be a string, in that case the TCP sock is
    bound to unix domain sock.

    The address parameter can also be a tuple of string and int, in that case
    the TCP sock is bound to host and port.
    If a host appears multiple times (possibly indirectly e.g. when hostnames
    resolve to the same IP address), the sock is only bound once to that
    host.

    This is a coroutine.

    :returns: `socket.socket` objects that listening on `address`.
    '''
    if net not in STREAM_OPTS:
        raise ValueError(f'only support {STREAM_OPTS.keys()} now, got {net}')

    sockets = []
    family, socket_kind = STREAM_OPTS[net]
    addr_infos = await getaddrinfo(address, family, socket_kind, flags)
    try:
        for addr_info in addr_infos:
            af, kind, proto, canonname, sa = addr_info
            try:
                sock = socket.socket(af, kind, proto)
            except socket.error:
                # Assume it's a bad family/type/protocol combination.
                continue
            sock.setblocking(False)
            set_sock_options(sock)
            if reuse_address:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            if settings.get('REUSE_PORT', ns='pymaid') or reuse_port:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            # Disable IPv4/IPv6 dual stack support (enabled by
            # default on Linux) which makes a single socket
            # listen on both address families.
            if HAS_IPv6_FAMILY and HAS_IPv6_PROTOCOL and af == socket.AF_INET6:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, True)

            if af == socket.AF_UNIX and os.path.exists(sa):
                os.unlink(sa)
            try:
                sock.bind(sa)
            except OSError as err:
                if err.errno == 98:
                    assert af == socket.AF_UNIX, af
                    raise OSError(
                        98,
                        (
                            'Address already in use; '
                            'pymaid cannot bind AF_UNIX parallelly'
                        )
                    ) from None
                raise OSError(
                    err.errno,
                    f'error occured while binding on address {addr_info}: '
                    f'{err.strerror}, addr_infos={addr_infos}'
                ) from None
            # see https://github.com/golang/go/issues/5030
            sock.listen(min(backlog, 65535))
            sockets.append(sock)
    except Exception:
        for sock in sockets:
            sock.close()
        raise

    if not sockets:
        raise socket.error('getaddrinfo returns an empty list')
    return sockets
