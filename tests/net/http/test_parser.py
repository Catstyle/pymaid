from pymaid.net.http.h11 import RequestParser, ResponseParser

from tests.common import http_data


def test_parse_request():
    parser = RequestParser()

    data = b'GET / HTTP/1.1\r\n\r\n'
    consumed = parser.feed_data(data)
    assert consumed == len(data)

    assert len(parser.queue) == 1
    req = parser.queue.popleft()
    assert req.method == 'GET'
    assert req.http_version == '1.1'
    assert len(req.headers) == 0

    consumed = parser.feed_data(http_data.REQUEST1)
    assert consumed == len(http_data.REQUEST1)

    assert len(parser.queue) == 1
    req = parser.queue.popleft()
    assert req.method == 'GET'
    assert req.http_version == '1.1'
    assert len(req.headers) == 2
    assert not req.chunked
    assert req.body == b''


def test_parse_chunked_request():
    parser = RequestParser()

    consumed = parser.feed_data(http_data.CHUNKED_REQUEST1_1)
    assert consumed == len(http_data.CHUNKED_REQUEST1_1)
    assert len(parser.queue) == 0

    consumed = parser.feed_data(http_data.CHUNKED_REQUEST1_2)
    assert consumed == len(http_data.CHUNKED_REQUEST1_2)

    assert len(parser.queue) == 1
    req = parser.queue.popleft()
    assert req.method == 'POST'
    assert req.uri.path == '/test.php'
    assert req.uri.query == 'a=b+c'
    assert req.http_version == '1.2'
    assert req.headers['transfer-encoding'] == 'chunked'
    assert req.chunked
    assert req.body == b'hello world'

    consumed = parser.feed_data(http_data.CHUNKED_REQUEST1_3)
    assert consumed == len(http_data.CHUNKED_REQUEST1_3)

    assert len(parser.queue) == 1
    req = parser.queue.popleft()
    assert req.chunked
    assert req.body == b'+\xce\xcfM\xb5MI,I\x04\x00'

    consumed = parser.feed_data(http_data.CHUNKED_REQUEST1_4)
    assert consumed == len(http_data.CHUNKED_REQUEST1_4)

    assert len(parser.queue) == 0
    req = parser.instance
    assert req.chunked
    assert req.headers['transfer-encoding'] == 'gzip, chunked'
    assert req.body == b'hello world'


def test_parse_upgrade_request():
    parser = RequestParser()

    consumed = parser.feed_data(http_data.UPGRADE_REQUEST1)
    assert consumed == http_data.UPGRADE_REQUEST1.index(b'\r\n\r\n') + 4

    assert len(parser.queue) == 1
    req = parser.queue.popleft()
    assert req.should_upgrade
    assert req.headers['connection'].lower() == 'upgrade'
    assert req.headers['upgrade'].lower() == 'websocket'


def test_parse_response():
    parser = ResponseParser()

    consumed = parser.feed_data(http_data.RESPONSE1_HEAD)
    assert consumed == len(http_data.RESPONSE1_HEAD)
    assert len(parser.queue) == 0

    consumed = parser.feed_data(http_data.RESPONSE1_BODY)
    assert consumed == len(http_data.RESPONSE1_BODY)

    assert len(parser.queue) == 1
    resp = parser.queue.popleft()
    assert resp.status_code == 200
    assert resp.status == 'OK'
    assert resp.headers['content-type'] == 'text/html;  charset=UTF-8'
    assert int(resp.headers['content-length']) == 130
    assert len(resp.body) == 130


def test_parse_upgrade_response():
    parser = ResponseParser()

    consumed = parser.feed_data(http_data.UPGRADE_RESPONSE1)
    assert consumed == http_data.UPGRADE_RESPONSE1.index(b'\r\n\r\n') + 4

    assert len(parser.queue) == 1
    resp = parser.queue.popleft()
    assert resp.should_upgrade
    assert resp.headers['connection'].lower() == 'upgrade'
    assert resp.headers['upgrade'].lower() == 'websocket'
    assert 'pymaid' in resp.headers['server'].lower()
    # A server MUST NOT send a Transfer-Encoding header field in any
    # response with a status code of 1xx (Informational) or 204 (No Content).
    assert not resp.chunked
    assert resp.body == b''
