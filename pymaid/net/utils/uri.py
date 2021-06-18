'''Inspired by `websockets`_.

.. _websockets: https://github.com/aaugustin/websockets/blob/main/src/websockets/uri.py  # noqa
'''
from dataclasses import dataclass
from os.path import isdir
from typing import Optional, Tuple
from urllib.parse import quote, urlsplit

# All characters from the gen-delims and sub-delims sets in RFC 3987.
DELIMS = ":/?#[]@!$&'()*+,;="
SCHEMES = {
    'unix', 'tcp', 'tcp4', 'tcp6', 'udp', 'udp4', 'udp6',
    'http', 'https', 'ws', 'wss',
    '',  # for url from content like `GET /whatever HTTP/1.1`
}


@dataclass
class URI:
    '''URI.

    :param str scheme: scheme
    :param str host: lower-case host
    :param int port: None for `unix` scheme,
        otherwise always set even if it's the default
    :param str path: path, `/` for default
    :param str query: optional query
    :param str fragment: optional query
    :param bool secure: secure flag
    :param str user_info: ``(username, password)`` tuple when the URI contains
        `User Information`_, else ``None``.
    :param str address: a combination of host:port for convenience

    .. _User Information: https://tools.ietf.org/html/rfc3986#section-3.2.1
    '''

    scheme: str
    host: str
    port: Optional[int]
    path: str
    query: str
    fragment: str
    secure: bool
    user_info: Optional[Tuple[str, str]]
    address: str


def parse_uri(uri: str) -> URI:
    '''Parse and validate URI.

    :raises ValueError: if ``uri`` is not a valid URI.
    '''
    parsed = urlsplit(uri)
    scheme = parsed.scheme

    # NOTE:
    #  unix/tcp/udp are layer 4 protocols
    # http/https/ws/wss are layer 7 protocols
    if scheme not in SCHEMES:
        raise ValueError(
            f'only {SCHEMES} scheme support now, '
            f'got uri={uri!r}, scheme={scheme!r}'
        )

    secure = scheme in {'https', 'wss'}
    # pymaid forced ipv6 address format like `[::1]`, sourrounded by `[]`
    host = f'[{parsed.hostname}]' if scheme.endswith('6') else parsed.hostname
    path = parsed.path or '/'
    query = parsed.query
    fragment = parsed.fragment

    if 'unix' == scheme:
        port = None
        # when using unix domain socket, assume path is the address
        if host:
            raise ValueError(
                f'`unix` scheme should not has host, '
                'e.g. unix:///absolute/path/to/sock; '
                f'got uri={uri!r} parsed={parsed!r}'
            )
        if not path or isdir(path):
            raise ValueError(
                '`unix` scheme should be with absolute path, '
                'e.g. unix:///absolute/path/to/sock; '
                f'got uri={uri!r} parsed={parsed!r}'
            )
        # used absolute path as host for unix scheme
        host = path
        path = '/'
    else:
        port = parsed.port or (443 if secure else 80)

    user_info = None
    if parsed.username is not None:
        # urlsplit accepts URLs with a username but without a password.
        # This doesn't make sense for HTTP Basic Auth credentials.
        if parsed.password is None:
            raise ValueError(
                'URI with a username but without a password makes no sense'
            )
        user_info = (parsed.username, parsed.password)

    try:
        uri.encode("ascii")
    except UnicodeEncodeError:
        # Input contains non-ASCII characters.
        # It must be an IRI. Convert it to a URI.
        host = host.encode("idna").decode()
        path = quote(path, safe=DELIMS)
        query = quote(query, safe=DELIMS)
        if user_info is not None:
            user_info = (
                quote(user_info[0], safe=DELIMS),
                quote(user_info[1], safe=DELIMS),
            )

    return URI(
        scheme,
        host,
        port,
        path,
        query,
        fragment,
        secure,
        user_info,
        f'{host}:{port}' if port else host,
    )
