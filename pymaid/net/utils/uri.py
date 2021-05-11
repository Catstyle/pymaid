'''Inspired by `websockets`_.

.. _websockets: https://github.com/aaugustin/websockets/blob/main/src/websockets/uri.py  # noqa
'''
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.parse import quote, urlsplit

# All characters from the gen-delims and sub-delims sets in RFC 3987.
DELIMS = ":/?#[]@!$&'()*+,;="


@dataclass
class URI:
    '''URI.

    :param str scheme: scheme
    :param str host: lower-case host
    :param int port: None for `file`,
        otherwise always set even if it's the default
    :param str path: path, `/` for default
    :param str query: optional query
    :param str fragment: optional query
    :param bool secure: secure flag
    :param str user_info: ``(username, password)`` tuple when the URI contains
        `User Information`_, else ``None``.

    :param str low_scheme: scheme that used in lower layer, current support
        only ``file`` scheme.

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

    low_scheme: Optional[str]


def parse_uri(uri: str) -> URI:
    '''Parse and validate URI.

    :raises ValueError: if ``uri`` is not a valid URI.
    '''
    parsed = urlsplit(uri)

    low_scheme = None
    scheme = parsed.scheme
    if '+' in scheme:
        assert scheme.count('+') == 1, 'not support multi `+` now'
        low_scheme, scheme = scheme.split('+')
        if low_scheme != 'file':
            raise ValueError('low_scheme now only support `file`')

    if scheme not in {'http', 'https', 'ws', 'wss', 'file', ''}:
        raise ValueError(
            'only {http, https, ws, wss, file} scheme support now, '
            f'got {uri!r}, {scheme!r}'
        )

    secure = scheme in {'https', 'wss'}
    host = parsed.hostname
    path = parsed.path or '/'
    query = parsed.query
    fragment = parsed.fragment

    if 'file' in {low_scheme, scheme}:
        port = None
        # when using unix domain socket, assume path is the address
        if host:
            raise ValueError(
                '`file` scheme should not has host, '
                'e.g. file:///absolute/path/to/sock'
            )
        if not path:
            raise ValueError(
                '`file` scheme should be with absolute path, ',
                'e.g. file:///absolute/path/to/sock'
            )
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
        low_scheme,
    )
