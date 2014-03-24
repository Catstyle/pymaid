from gevent.event import AsyncResult
from gevent import socket
from gevent.hub import get_hub
from gevent import core

from google.protobuf.service import RpcChannel
from google.protobuf.message import DecodeError

from pymaid.controller import Controller
from pymaid.connection import Connection


class Channel(RpcChannel):

    MAX_CONCURRENCY = 10000

    def __init__(self, host='localhost', port=0, loop=None):
        super(Channel, self).__init__()

        self._transmission_id = 0
        self._loop = loop or get_hub().loop
        self._host_address = (host, port)

        self._connections = []
        self._services = {}
        self._pending_request = {}

    def CallMethod(self, method, controller, request, response_class, done):
        assert isinstance(controller, Controller), controller

        controller.async_result = AsyncResult()
        if controller.conn not in self._connections:
            controller.SetFailed("did not connect")
            controller.async_result.set(None)
            return controller.async_result

        controller.meta_data.stub = True
        controller.meta_data.service_name = method.containing_service.full_name
        controller.meta_data.method_name = method.name

        transmission_id = self.get_transmission_id()
        controller.response_class = response_class
        controller.meta_data.transmission_id = transmission_id

        assert transmission_id not in self._pending_request
        self._pending_request[transmission_id] = controller

        controller.conn.send(controller)
        return controller.async_result

    def append_service(self, service):
        self._services[service.DESCRIPTOR.full_name] = service

    def get_transmission_id(self):
        self._transmission_id += 1
        if self._transmission_id >= (1 << 63) -1:
            self._transmission_id = 0
        return self._transmission_id

    def listen(self, host, port, backlog=1):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(backlog)
        sock.setblocking(0)
        accept_watcher = self._loop.io(sock.fileno(), core.READ)
        accept_watcher.start(self._do_accept, sock)

    def new_connection(self, sock=None):
        if sock is None:
            sock = self._create_sock()
        conn = Connection(sock)
        #print 'new_connection', sock
        assert conn not in self._connections

        conn.set_close_cb(self.close_connection)
        conn.set_request_cb(self._handle_request)
        conn.set_response_cb(self._handle_response)
        self._connections.append(conn)
        return conn

    def close_connection(self, conn, reason=None):
        #print 'close_connection', (conn, reason)
        assert conn in self._connections
        conn.close()
        self._connections.remove(conn)
        # TODO: clean pending_request if needed
        #del self._pending_request[transmission_id]

    def _create_sock(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        cnt, max_retry = 0, 3
        while 1:
            try:
                sock.connect(self._host_address)
            except socket.error as err:
                #print 'socket error', err
                cnt += 1
                if err.args[0] == socket.EWOULDBLOCK and cnt < max_retry:
                    continue
                raise
            else:
                break
        return sock

    def _do_accept(self, sock):
        try:
            client_socket, address = sock.accept()
        except socket.error as err:
            if err.args[0] == socket.EWOULDBLOCK:
                return
            raise
        self.new_connection(client_socket)

    def _handle_request(self, controller, message_buffer):
        service = self._services.get(controller.meta_data.service_name, None)
        controller.meta_data.stub = False
        conn = controller.conn

        if service is None:
            controller.SetFailed("service not exist")
            conn.send(controller)
            return

        method = service.DESCRIPTOR.FindMethodByName(
                controller.meta_data.method_name)
        if method is None:
            controller.SetFailed("method not exist")
            conn.send(controller)
            return

        request_class = service.GetRequestClass(method)
        request = request_class()
        request.ParseFromString(message_buffer)

        response = service.CallMethod(method, controller, request, None)
        controller.response = response
        conn.send(controller)

    def _handle_response(self, controller_, message_buffer):
        transmission_id = controller_.meta_data.transmission_id
        controller = self._pending_request.get(transmission_id, None)
        if controller is None:
            return
        del self._pending_request[transmission_id]

        controller.meta_data.MergeFrom(controller_.meta_data)
        if controller.Failed():
            controller.async_result.set(None)
            return

        response = controller.response_class()
        try:
            response.ParseFromString(message_buffer)
        except DecodeError as ex:
            controller.SetFailed(ex)
            controller.async_result.set_exception(ex)
        controller.async_result.set(response)
