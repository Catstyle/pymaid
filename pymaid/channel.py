from gevent.event import AsyncResult
from gevent import socket
from gevent import wait
from gevent.core import READ
from gevent.hub import get_hub

from google.protobuf.service import RpcChannel
from google.protobuf.message import DecodeError

from pymaid.connection import Connection
from pymaid.apps.monitor import MonitorServiceImpl
from pymaid.error import BaseMeta, BaseError, ServiceNotExist, MethodNotExist
from pymaid.utils import greenlet_pool, logger_wrapper
from pymaid.pb.pymaid_pb2 import Void, ErrorMessage


@logger_wrapper
class Channel(RpcChannel):

    # Sets the maximum number of consecutive accepts that a process may perform
    # on a single wake up. High values give higher priority to high connection
    # rates, while lower values give higher priority to already established
    # connections.
    # Default is 100. Note, that in case of multiple working processes on the
    # same listening value, it should be set to a lower value.
    # (pywsgi.WSGIServer sets it to 1 when environ["wsgi.multiprocess"] is true)
    MAX_ACCEPT = 100
    MAX_CONCURRENCY = 10000

    def __init__(self, loop=None):
        super(Channel, self).__init__()

        self._transmission_id = 0
        self._pending_results = {}
        self._loop = loop or get_hub().loop

        self._income_connections = {}
        self._outcome_connections = {}
        self.services = {}

        self.need_heartbeat = False
        self.heartbeat_interval = 0
        self.max_heartbeat_timeout_count = 0

    def CallMethod(self, method, controller, request, response_class, done):
        controller.meta_data.from_stub = True
        controller.meta_data.service_name = method.containing_service.full_name
        controller.meta_data.method_name = method.name
        if not isinstance(request, Void):
            controller.meta_data.request = request.SerializeToString()

        transmission_id = self.get_transmission_id()
        assert transmission_id not in self._pending_results
        controller.meta_data.transmission_id = transmission_id

        # broadcast
        if controller.wide:
            for conn in self._income_connections:
                conn.send(controller)
        elif controller.group:
            get_conn = self.get_income_connection
            for conn_id in controller.group:
                conn = get_conn(conn_id, None)
                if conn:
                    conn.send(controller)
        else:
            #if controller.conn.conn_id not in self._outcome_connections:
            #    raise Exception('did not connect')
            controller.conn.send(controller)

        if issubclass(response_class, Void):
            return None

        async_result = AsyncResult()
        self._pending_results[transmission_id] = async_result, response_class
        return async_result.get()

    def append_service(self, service):
        assert service.DESCRIPTOR.full_name not in self.services
        self.services[service.DESCRIPTOR.full_name] = service

    def enable_heartbeat(self, heartbeat_interval, max_timeout_count):
        assert heartbeat_interval > 0
        assert max_timeout_count >= 1
        self.need_heartbeat = True
        self.heartbeat_interval = heartbeat_interval
        self.max_heartbeat_timeout_count = max_timeout_count
        # TODO: enable all connections heartbeat?

    def disable_heartbeat(self):
        self.need_heartbeat = False
        self.heartbeat_interval = 0
        self.max_heartbeat_timeout_count = 0
        # TODO: disable all connections heartbeat?

    def get_income_connection(self, conn_id):
        return self._income_connections.get(conn_id)
    
    def get_outcome_connection(self, conn_id):
        return self._outcome_connections.get(conn_id)

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
        conn = self.new_connection(sock, server_side=False)
        return conn

    def listen(self, host, port, backlog=256):
        self._setup_server()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(backlog)
        sock.setblocking(0)
        accept_watcher = self._loop.io(sock.fileno(), READ)
        accept_watcher.start(self._do_accept, sock)

    def new_connection(self, sock, server_side):
        conn = Connection(sock, server_side)
        #print 'new_connection', conn.conn_id
        if server_side:
            assert conn.conn_id not in self._income_connections
            self._income_connections[conn.conn_id] = conn
        else:
            assert conn.conn_id not in self._outcome_connections
            self._outcome_connections[conn.conn_id] = conn

        conn.set_close_cb(self.close_connection)
        greenlet_pool.spawn(self._handle_loop, conn)
        self._setup_heartbeat(conn, server_side)
        return conn

    def close_connection(self, conn, reason=None):
        #print 'close_connection', (conn.conn_id, reason)
        conn.close()
        if conn.server_side:
            assert conn.conn_id in self._income_connections
            del self._income_connections[conn.conn_id]
        else:
            assert conn.conn_id in self._outcome_connections
            del self._outcome_connections[conn.conn_id]
        # TODO: clean pending_results if needed
        #del self._pending_results[transmission_id]

    def serve_forever(self):
        wait()

    @property
    def is_full(self):
        return len(self._income_connections) == self.MAX_CONCURRENCY

    def _setup_server(self):
        # only server need monitor service
        monitor_service = MonitorServiceImpl()
        monitor_service.channel = self
        self.append_service(monitor_service)

    def _setup_heartbeat(self, conn, server_side):
        if server_side:
            if self.need_heartbeat:
                conn.setup_server_heartbeat(
                    self.heartbeat_interval, self.max_heartbeat_timeout_count
                )
        else:
            conn.setup_client_heartbeat(channel=self)

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
            self.new_connection(client_socket, server_side=True)

    def _handle_loop(self, conn):
        recv = conn.recv
        recv_request, recv_response = self._recv_request, self._recv_response
        try:
            while 1:
                controller = recv()
                if not controller:
                    break
                if controller.meta_data.from_stub: # request
                    try:
                        recv_request(controller)
                    except BaseError as ex:
                        controller.SetFailed(ex)
                        conn.send(controller)
                else:
                    recv_response(controller)
        except Exception as ex:
            self.logger.exception(ex)
            raise
        finally:
            conn.close()

    def _recv_request(self, controller):
        meta_data = controller.meta_data
        meta_data.from_stub = False
        service = self.services.get(meta_data.service_name, None)
        conn = controller.conn

        if service is None:
            raise ServiceNotExist(service_name=meta_data.service_name)

        method = service.DESCRIPTOR.FindMethodByName(meta_data.method_name)
        if method is None:
            raise MethodNotExist(service_name=meta_data.service_name,
                                 method_name=meta_data.method_name)

        request_class = service.GetRequestClass(method)
        request = request_class()
        request.ParseFromString(meta_data.request)

        def send_back(response):
            response_class = service.GetResponseClass(method)
            if issubclass(response_class, Void):
                assert response is None
            else:
                meta_data.response = response.SerializeToString()
                conn.send(controller)
        service.CallMethod(method, controller, request, send_back)

    def _recv_response(self, controller):
        transmission_id = controller.meta_data.transmission_id
        pending_result = self._pending_results.get(transmission_id, (None, None))
        async_result, response_class = pending_result
        if async_result is None:
            return
        del self._pending_results[transmission_id]

        if controller.Failed():
            error_message = ErrorMessage()
            error_message.ParseFromString(controller.meta_data.error_text)
            cls = BaseMeta.get_by_code(error_message.error_code)
            ex = cls()
            ex.message = error_message.error_message
            async_result.set_exception(ex)
            return

        response = response_class()
        try:
            response.ParseFromString(controller.meta_data.response)
        except DecodeError as ex:
            async_result.set_exception(ex)
        else:
            async_result.set(response)
