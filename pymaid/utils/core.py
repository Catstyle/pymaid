from gevent import get_hub


hub = get_hub()
timer = hub.loop.timer
io = hub.loop.io
del hub
