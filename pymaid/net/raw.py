'''Raw socket layer.

Mostly inspired from standard lib `asyncio`.
'''

import os
import socket

from errno import ENOTCONN, ECONNABORTED
from typing import List, Tuple, Union

from pymaid.core import get_running_loop, run_in_threadpool

HAS_IPv6_FAMILY = hasattr(socket, 'AF_INET6')
HAS_IPv6_PROTOCOL = hasattr(socket, 'IPPROTO_IPV6')


async def sock_connect(address: Tuple[str, int]) -> socket.socket:
    if isinstance(address, str):
        infos = [(socket.AF_UNIX, socket.SOCK_STREAM, 0, '', address)]
    else:
        host, port = address
        infos = await run_in_threadpool(
            socket.getaddrinfo, args=(host, port, 0, socket.SOCK_STREAM),
        )
    loop = get_running_loop()
    err = None
    for res in infos:
        af, socktype, proto, canonname, sa = res
        sock = None
        retried = False
        while 1:
            try:
                sock = socket.socket(af, socktype, proto)
                sock.setblocking(False)
                await loop.sock_connect(sock, sa)
                if socktype == socket.SOCK_STREAM and af != socket.AF_UNIX:
                    sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                # NOTE:
                # when doing a lots connect to remote side under heavy pressure
                # it would sometimes getting ENOTCONN when call getpeername
                # check it here, if occured, raise it to retry
                # *why* sock_connect above does not handle this case?
                sock.getpeername()
                # Break explicitly a reference cycle
                err = None
                return sock
            except socket.error as _:
                if _.errno in {ECONNABORTED, ENOTCONN} and not retried:
                    retried = True
                    continue
                err = _
                if sock is not None:
                    sock.close()
                break

    if err is not None:
        try:
            raise err
        finally:
            # Break explicitly a reference cycle
            err = None
    else:
        raise socket.error('getaddrinfo returns an empty list')


async def sock_listen(
    address: Union[Tuple[str, int], str],
    family: socket.AddressFamily = socket.AF_UNSPEC,
    flags: socket.AddressInfo = socket.AI_PASSIVE,
    backlog: int = 128,
    reuse_address: bool = True,
    reuse_port: bool = False,
) -> List[socket.socket]:
    '''Create sockets listening on `address`.

    The address parameter can be a string, in that case the TCP server is
    bound to unix domain sock.

    The address parameter can also be a tuple of string and int, in that case
    the TCP server is bound to host and port.
    If a host appears multiple times (possibly indirectly e.g. when hostnames
    resolve to the same IP address), the server is only bound once to that
    host.

    Return a Server object which can be used to stop the service.

    This is a coroutine.
    '''
    sockets = []

    if isinstance(address, str):
        if os.path.exists(address):
            os.unlink(address)
        infos = [(socket.AF_UNIX, socket.SOCK_STREAM, 0, '', address)]
    else:
        host, port = address
        infos = await run_in_threadpool(
            socket.getaddrinfo,
            args=(host, port, family, socket.SOCK_STREAM),
            kwargs={'flags': flags},
        )
        infos = set(infos)
    try:
        for res in infos:
            af, socktype, proto, canonname, sa = res
            try:
                sock = socket.socket(af, socktype, proto)
            except socket.error:
                # Assume it's a bad family/type/protocol combination.
                continue
            sock.setblocking(False)
            if socktype == socket.SOCK_STREAM and af != socket.AF_UNIX:
                sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            if reuse_address:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            if reuse_port:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            # Disable IPv4/IPv6 dual stack support (enabled by
            # default on Linux) which makes a single socket
            # listen on both address families.
            if HAS_IPv6_FAMILY and HAS_IPv6_PROTOCOL and af == socket.AF_INET6:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, True)
            try:
                sock.bind(sa)
            except OSError as err:
                raise OSError(
                    err.errno,
                    f'error while binding on address {infos}: {err.strerror}'
                ) from None
            sock.listen(backlog)
            sockets.append(sock)
    except Exception:
        for sock in sockets:
            sock.close()
        raise

    if not sockets:
        raise socket.error('getaddrinfo returns an empty list')
    return sockets
