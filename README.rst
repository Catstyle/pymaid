======
pymaid
======

A useful toolset.

Features
--------

* low level transport/protocol
* high level stream/websocket
* rpc support
* custom combination of transport and protocol
* useful ErrorManager
* useful settings module
* pluggable extensions, such as MiddlewareManager
* handy `pymaid` console script
* best effort performance
* keep simple for use


Installation
------------

.. code-block::

   pip install -U pymaid


Examples
--------

.. code-block:: python

   import pymaid
   from pymaid.net.stream import Stream

   from examples.template import get_server_parser, parse_args


   class Stream(Stream):

       def data_received(self, data):
           # cannot use asynchronous way since this is in io callback
           self.write_sync(data)


   async def main():
       args = parse_args(get_server_parser())
       ch = await pymaid.net.serve_stream(args.address, transport_class=Stream)
       async with ch:
           await ch.serve_forever()


   if __name__ == "__main__":
       pymaid.run(main())
