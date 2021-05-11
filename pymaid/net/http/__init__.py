from typing import IO


def parse_request(buf: IO):
    pass


def parse_response(buf: IO):
    pass


def parse_headers(buf: IO):
    headers = {}
    readline = buf.readline
    while 1:
        line = readline(1024)
        if line == b'\r\n':
            break
        line = line.strip()
        if not line:
            # empty string, not enough data
            headers = {}
            break
        key, value = line.split(b':', 1)
        headers[key] = value.strip()
    return headers
