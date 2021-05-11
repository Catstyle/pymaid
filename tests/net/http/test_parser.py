from pymaid.net.http.h11 import RequestParser, ResponseParser

from tests.common import http_data


def test_parse_request():
    parser = RequestParser()

    _, data = parser.feed_data(http_data.CHUNKED_REQUEST1_1)
    _, data = parser.feed_data(http_data.CHUNKED_REQUEST1_2)
    assert len(data) == 1

    req = data[0]
    assert req.method == 'POST'
    assert req.uri.path == '/test.php'
    assert req.uri.query == 'a=b+c'
    assert req.http_version == '1.2'

    _, data = parser.feed_data(http_data.UPGRADE_REQUEST1)
    assert len(data) == 1
    req = data[0]

    assert req.should_upgrade


def test_parse_response():
    parser = ResponseParser()

    _, data = parser.feed_data(http_data.RESPONSE1_HEAD)
    assert len(data) == 0

    _, data = parser.feed_data(http_data.RESPONSE1_BODY)
    assert len(data) == 1

    resp = data[0]
    assert resp.status_code == 200
    assert resp.status == 'OK'
