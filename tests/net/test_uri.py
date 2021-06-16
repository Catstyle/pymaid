import pytest
from pymaid.net.utils.uri import parse_uri


def test_http_uri():
    uri = parse_uri('http://google.com')

    assert uri.scheme == 'http'
    assert uri.host == 'google.com'
    assert uri.port == 80
    assert uri.path == '/', 'default path should be `/`'
    assert uri.query == ''
    assert uri.secure is False
    assert uri.user_info is None

    uri = parse_uri('http://cat:dog@google.com/search?q=pymaid#what')

    assert uri.scheme == 'http'
    assert uri.host == 'google.com'
    assert uri.port == 80
    assert uri.path == '/search'
    assert uri.query == 'q=pymaid'
    assert uri.fragment == 'what'
    assert uri.secure is False
    assert uri.user_info == ('cat', 'dog')


def test_https_uri():
    uri = parse_uri('https://google.com')

    assert uri.scheme == 'https'
    assert uri.host == 'google.com'
    assert uri.port == 443
    assert uri.path == '/', 'default path should be `/`'
    assert uri.query == ''
    assert uri.secure is True
    assert uri.user_info is None

    uri = parse_uri('https://cat:dog@google.com/search?q=pymaid#what')

    assert uri.scheme == 'https'
    assert uri.host == 'google.com'
    assert uri.port == 443
    assert uri.path == '/search'
    assert uri.query == 'q=pymaid'
    assert uri.fragment == 'what'
    assert uri.secure is True
    assert uri.user_info == ('cat', 'dog')


def test_ws_uri():
    uri = parse_uri('ws://google.com')

    assert uri.scheme == 'ws'
    assert uri.host == 'google.com'
    assert uri.port == 80
    assert uri.path == '/', 'default path should be `/`'
    assert uri.query == ''
    assert uri.secure is False
    assert uri.user_info is None

    uri = parse_uri('ws://cat:dog@google.com/search?q=pymaid#what')

    assert uri.scheme == 'ws'
    assert uri.host == 'google.com'
    assert uri.port == 80
    assert uri.path == '/search'
    assert uri.query == 'q=pymaid'
    assert uri.fragment == 'what'
    assert uri.secure is False
    assert uri.user_info == ('cat', 'dog')


def test_wss_uri():
    uri = parse_uri('wss://google.com')

    assert uri.scheme == 'wss'
    assert uri.host == 'google.com'
    assert uri.port == 443
    assert uri.path == '/', 'default path should be `/`'
    assert uri.query == ''
    assert uri.secure is True
    assert uri.user_info is None

    uri = parse_uri('wss://cat:dog@google.com/search?q=pymaid#what')

    assert uri.scheme == 'wss'
    assert uri.host == 'google.com'
    assert uri.port == 443
    assert uri.path == '/search'
    assert uri.query == 'q=pymaid'
    assert uri.fragment == 'what'
    assert uri.secure is True
    assert uri.user_info == ('cat', 'dog')


def test_unix_uri():
    uri = parse_uri('unix:///path/to/file')

    assert uri.scheme == 'unix'
    assert uri.host == '/path/to/file'
    assert uri.port == 0
    assert uri.path == '/', 'default path should be `/`'
    assert uri.query == ''
    assert uri.secure is False
    assert uri.user_info is None

    uri = parse_uri('unix://cat:dog@/path/to/file?q=pymaid#what')

    assert uri.scheme == 'unix'
    assert uri.host == '/path/to/file'
    assert uri.port == 0
    assert uri.path == '/', 'default path should be `/`'
    assert uri.query == 'q=pymaid'
    assert uri.fragment == 'what'
    assert uri.secure is False
    assert uri.user_info == ('cat', 'dog')

    with pytest.raises(ValueError):
        # relative path
        parse_uri('unix://path/to/file')
    with pytest.raises(ValueError):
        # no path
        parse_uri('unix://')
