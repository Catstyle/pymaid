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
