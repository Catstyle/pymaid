from gevent.event import AsyncResult
from gevent import socket
from gevent.hub import get_hub

from google.protobuf.service import RpcChannel
from google.protobuf.message import DecodeError

from pymaid.controller import Controller
from pymaid.connection import Connection
from pymaid.utils import greenlet_pool, logger_wrapper
from pymaid.pb.pymaid_pb2 import Void


@logger_wrapper
class Channel(RpcChannel):

    # Sets the maximum number of consecutive accepts that a process may perform on
    # a single wake up. High values give higher priority to high connection rates,
    # while lower values give higher priority to already established connections.
    # Default is 100. Note, that in case of multiple working processes on the same
    # listening value, it should be set to a lower value. (pywsgi.WSGIServer sets it
    # to 1 when environ["wsgi.multiprocess"] is true)
    MAX_ACCEPT = 100
    MAX_CONCURRENCY = 10000

    def __init__(self, loop=None):
        super(Channel, self).__init__()

        self._transmission_id = 0
        self._loop = loop or get_hub().loop

        self._connections = {}
        self._services = {}
        self._pending_results = {}

    def CallMethod(self, method, controller, request, response_class, done):
        assert isinstance(controller, Controller), controller

        controller.meta_data.stub = True
        controller.meta_data.service_name = method.containing_service.full_name
        controller.meta_data.method_name = method.name
        if not isinstance(request, Void):
            controller.request = request

        transmission_id = self.get_transmission_id()
        assert transmission_id not in self._pending_results
        controller.meta_data.transmission_id = transmission_id

        if controller.wide:
            for conn in self._connections:
                conn.send(controller)
        elif controller.group:
            get_conn = self.get_connection_by_id
            for conn_id in controller.group:
                conn = get_conn(conn_id, None)
                if conn:
                    conn.send(controller)
        else:
            if controller.conn.conn_id not in self._connections:
                raise Exception('did not connect')
            controller.conn.send(controller)

        if issubclass(response_class, Void):
            return None

        async_result = AsyncResult()
        self._pending_results[transmission_id] = async_result, response_class
        return async_result.get()

    def append_service(self, service):
        self._services[service.DESCRIPTOR.full_name] = service

    def get_connection_by_id(self, conn_id):
        return self._connections.get(conn_id, None)

    def get_transmission_id(self):
        self._transmission_id += 1
        if self._transmission_id >= 2 ** 32:
            self._transmission_id = 0
        return self._transmission_id

    def connect(self, host, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        cnt, max_retry = 0, 3
        while 1:
            try:
                sock.connect((host, port))
            except socket.error as err:
                #print 'socket error', err
                cnt += 1
                if err.args[0] == socket.EWOULDBLOCK and cnt < max_retry:
                    continue
                raise
            else:
                break
        conn = self.new_connection(sock)
        return conn

    def listen(self, host, port, backlog=256):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(backlog)
        sock.setblocking(0)
        # from gevent.core import READ
        # changed to 1 to make running on pypy+gevent
        #accept_watcher = self._loop.io(sock.fileno(), READ)
        accept_watcher = self._loop.io(sock.fileno(), 1)
        accept_watcher.start(self._do_accept, sock)

    def new_connection(self, sock):
        conn = Connection(sock)
        #print 'new_connection', conn.conn_id
        assert conn.conn_id not in self._connections

        conn.set_close_cb(self.close_connection)
        greenlet_pool.spawn(self._handle_loop, conn)
        self._connections[conn.conn_id] = conn
        return conn

    def close_connection(self, conn, reason=None):
        #print 'close_connection', (conn.conn_id, reason)
        assert conn.conn_id in self._connections
        conn.close()
        del self._connections[conn.conn_id]
        # TODO: clean pending_results if needed
        #del self._pending_results[transmission_id]

    @property
    def is_full(self):
        return len(self._connections) == self.MAX_CONCURRENCY

    def _do_accept(self, sock):
        for _ in xrange(self.MAX_ACCEPT):
            if self.is_full:
                return
            try:
                client_socket, address = sock.accept()
            except socket.error as ex:
                if ex.args[0] == socket.EWOULDBLOCK:
                    return
                #self.logger.exception(ex)
                raise
            self.new_connection(client_socket)

    def _handle_loop(self, conn):
        recv = conn.recv
        recv_request, recv_response = self._recv_request, self._recv_response
        try:
            while 1:
                controller, message_buffer = recv()
                if not controller:
                    break
                if controller.meta_data.stub: # request
                    recv_request(controller, message_buffer)
                else:
                    recv_response(controller, message_buffer)
        except Exception as ex:
            self.logger.exception(ex)
            raise
        finally:
            conn.close()

    def _recv_request(self, controller, message_buffer):
        #print 'recv_request', controller, message_buffer
        service = self._services.get(controller.meta_data.service_name, None)
        controller.meta_data.stub = False
        conn = controller.conn

        if service is None:
            controller.SetFailed("service not exist")
            conn.send(controller)
            return

        method = service.DESCRIPTOR.FindMethodByName(controller.meta_data.method_name)
        if method is None:
            controller.SetFailed("method not exist")
            conn.send(controller)
            return

        request_class = service.GetRequestClass(method)
        request = request_class()
        request.ParseFromString(message_buffer)

        response = service.CallMethod(method, controller, request, None)
        response_class = service.GetResponseClass(method)
        if issubclass(response_class, Void):
            assert response is None
        else:
            controller.response = response
            conn.send(controller)

    def _recv_response(self, controller, message_buffer):
        #print 'recv_response', controller, message_buffer
        transmission_id = controller.meta_data.transmission_id
        pending_result = self._pending_results.get(transmission_id, (None, None))
        async_result, response_class = pending_result
        if async_result is None:
            return
        del self._pending_results[transmission_id]

        if controller.Failed():
            # TODO: construct Error/Warning based on error_text
            error_text = controller.meta_data.error_text
            async_result.set(error_text)
            return

        response = response_class()
        try:
            response.ParseFromString(message_buffer)
        except DecodeError as ex:
            #controller.SetFailed(ex)
            async_result.set_exception(ex)
        else:
            async_result.set(response)
