class BaseMiddleware(object):

    def on_connect(self, conn):
        raise NotImplementedError()

    def on_close(self, conn):
        raise NotImplementedError()
