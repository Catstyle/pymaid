import traceback

from io import BytesIO

import httptools

from . import BaseProtocol


CRITICAL_ERROR_TEXT = '''HTTP/1.0 500 INTERNAL SERVER ERROR
Server: pymaid
X-Powered-By: pymaid
X-HTTP-Backend: httptools
Content-Type: text/html; charset=utf-8
Content-Length: 127

<!DOCTYPE HTML PUBLIC '-//W3C//DTD HTML 3.2 Final//EN'>
<title>Internal Server Error</title>
<h1>Internal Server Error</h1>
'''.replace('\n', '\r\n')

HTTP_SWITCHING_PROTOCOLS = '''HTTP/1.1 101 SWITCHING PROTOCOLS
Connection: Upgrade
Upgrade: h2c
Server: pymaid
X-Powered-By: pymaid
X-HTTP-Backend: httptools
Content-Length: 0

'''.replace('\n', '\r\n')

HTTP_TOO_BIG = '''HTTP/1.1 413 PAYLOAD TOO LARGE
Server: pymaid
X-Powered-By: pymaid
X-HTTP-Backend: httptools
Content-Length: 0

'''.replace('\n', '\r\n')

HTTP_INVALID_COMPRESSION = '''HTTP/1.1 400 BAD REQUEST
Server: pymaid
X-Powered-By: pymaid
X-HTTP-Backend: httptools
Content-Length: 25

Invalid compressed data
'''.replace('\n', '\r\n')


class HttpParser:

    MAX_BODY_SIZE = 10 * 1024 * 1024

    def __init__(self, transport, handler):
        self.transport = transport
        self.handler = handler

    # httptools callbacks
    def on_message_begin(self):
        ''' Called when a message begins. '''
        self.body = BytesIO()
        self.headers = []

    def on_header(self, name: bytes, value: bytes):
        ''' Called when a header has been received.

        :param name: The name of the header.
        :param value: The value of the header.
        '''
        self.headers.append((name.decode(), value.decode()))

    def on_headers_complete(self):
        ''' Called when the headers have been completely sent. '''

    def on_body(self, body: bytes):
        ''' Called when part of the body has been received.

        :param body: The body text.
        '''
        self.body.write(body)
        if self.body.tell() >= self.MAX_BODY_SIZE:
            # write a 'too big' message
            self.write(HTTP_TOO_BIG)
            self.close()

    def on_chunk_header(self):
        pass

    def on_chunk_complete(self):
        pass


class HttpRequest(HttpParser):

    def on_message_begin(self):
        super().on_message_begin()
        self.full_url = ''

    def on_url(self, url: bytes):
        self.full_url = url.decode('utf-8')

    def on_message_complete(self):
        await self.handler.handle_request(self)


class HttpResponse(HttpParser):

    def on_message_begin(self):
        super().on_message_begin()
        self.status = 0

    def on_status(self, url: bytes):
        self.full_url = url.decode('utf-8')

    def on_message_complete(self):
        await self.handler.handle_response(self)


class HTTP(BaseProtocol):

    def __init__(self, handler):
        super().__init__(handler)
        self.request_parser = httptools.HttpRequestParser(HttpRequest(handler))
        self.response_parser = httptools.HttpResponseParser(
            HttpResponse(handler)
        )

    def data_received(self, data: bytes):
        try:
            self.parser.feed_data(data)
        except httptools.HttpParserUpgrade:
            self.handle_upgrade()
        except httptools.HttpParserError as exc:
            traceback.print_exc()
            self.handle_parser_exception(exc)

    def handle_parser_exception(self, exc):
        pass

    def handle_upgrade(self):
        pass
