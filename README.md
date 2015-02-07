pymaid
======

a rpc framework based on gevent and google protocol buffer


packet format
======

basic format: |---1 byte---|-1 byte-|----------4 bytes--------------|-----n bytes----|
description : |---parser---|--type--|-Controller length(Big Endian)-|---Controller---|
