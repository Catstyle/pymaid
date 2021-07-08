======
pymaid
======

A handy toolset.

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


   class Stream(Stream):

       def data_received(self, data):
           # cannot use asynchronous way since this is in io callback
           self.write_sync(data)


   async def main():
       ch = await pymaid.net.serve_stream(
           'tcp://127.0.0.1:8001', transport_class=Stream
       )
       async with ch:
           await ch.serve_forever()


   if __name__ == "__main__":
       pymaid.run(main())


.. code-block:: python

   import pymaid
   from pymaid.net.stream import Stream


   class Stream(Stream):

       def init(self):
           self.data_size = 0

       def data_received(self, data):
           self.data_size += len(data)


   async def wrapper(address, count):
       stream = await pymaid.net.dial_stream(address, transport_class=Stream)

       for _ in range(count):
           await stream.write(b'a' * 1000)
       stream.shutdown()
       await stream.wait_closed()
       assert stream.data_size == 1000 * count, (stream.data_size, 1000 * count)


   async def main():
       tasks = []
       address = 'tcp://127.0.0.1:8001'
       for x in range(100):
           tasks.append(pymaid.create_task(wrapper(address, 1000)))

       # await pymaid.wait(tasks, timeout=args.timeout)
       await pymaid.gather(*tasks)


   if __name__ == "__main__":
       pymaid.run(main())
