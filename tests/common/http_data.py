RESPONSE1_HEAD = b'''HTTP/1.1 200 OK
Date: Mon, 23 May 2005 22:38:34 GMT
Server: Apache/1.3.3.7
        (Unix) (Red-Hat/Linux)
Last-Modified: Wed, 08 Jan 2003 23:11:55 GMT
ETag: "3f80f-1b6-3e1cb03b"
Content-Type: text/html;
  charset=UTF-8
Content-Length: 130
Accept-Ranges: bytes
Connection: close

'''

RESPONSE1_BODY = b'''
<html>
<head>
  <title>An Example Page</title>
</head>
<body>
  Hello World, this is a very simple HTML document.
</body>
</html>'''


CHUNKED_REQUEST1_1 = b'''POST /test.php?a=b+c HTTP/1.2
User-Agent: Fooo
Host: bar
Transfer-Encoding: chunked

5\r\nhello\r\n6\r\n world\r\n'''

CHUNKED_REQUEST1_2 = b'''0\r\nVary: *\r\nUser-Agent: spam\r\n\r\n'''

CHUNKED_REQUEST1_3 = b'''POST /test.php?a=b+c HTTP/1.2
User-Agent: Fooo
Host: bar
Transfer-Encoding: chunked

b\r\n+\xce\xcfM\xb5MI,I\x04\x00\r\n0\r\n\r\n'''


UPGRADE_REQUEST1 = b'''GET /demo HTTP/1.1
Host: example.com
Connection: Upgrade
Sec-WebSocket-Key2: 12998 5 Y3 1  .P00
Sec-WebSocket-Protocol: sample
Upgrade: WebSocket
Sec-WebSocket-Key1: 4 @1  46546xW%0l 1 5
Origin: http://example.com

Hot diggity dogg'''

UPGRADE_RESPONSE1 = b'''HTTP/1.1 101 Switching Protocols
UPGRADE: websocket
SEC-WEBSOCKET-ACCEPT: rVg+XakFNFOxk3ZH0lzrZBmg0aU=
TRANSFER-ENCODING: chunked
CONNECTION: upgrade
DATE: Sat, 07 May 2016 23:44:32 GMT
SERVER: Python/3.4 aiohttp/1.0.3

data'''.replace(b'\n', b'\r\n')
