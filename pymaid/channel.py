__all__ = ['Channel']

from gevent.event import AsyncResult
from gevent import socket
from gevent import wait
from gevent.core import READ, MAXPRI
from gevent.hub import get_hub

from google.protobuf.service import RpcChannel
from google.protobuf.message import DecodeError

from pymaid.connection import Connection
from pymaid.controller import Controller
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
    MAX_ACCEPT = 1024
    MAX_CONCURRENCY = 30000

    def __init__(self, loop=None):
        super(Channel, self).__init__()

        self.transmission_id = 0
        self.pending_results = {}
        self.loop = loop or get_hub().loop

        self._income_connections = {}
        self._outcome_connections = {}
        self.services = {}

        self.need_heartbeat = False
        self.heartbeat_interval = 0
        self.max_heartbeat_timeout_count = 0

    def CallMethod(self, method, controller, request, response_class, done):
        meta_data = controller.meta_data
        meta_data.from_stub = True
        meta_data.service_name = method.containing_service.full_name
        meta_data.method_name = method.name
        if not isinstance(request, Void):
            meta_data.message = request.SerializeToString()

        require_response = not issubclass(response_class, Void)
        if require_response:
            transmission_id = self.transmission_id
            self.transmission_id += 1
            meta_data.transmission_id = transmission_id

        packet = meta_data.SerializeToString()
        if controller.wide:
            # broadcast
            for conn in self._income_connections.itervalues():
                conn.send(packet)
        elif controller.group:
            # small broadcast
            get_conn = self.get_income_connection
            for conn_id in controller.group:
                conn = get_conn(conn_id)
                if conn:
                    conn.send(packet)
        else:
            controller.conn.send(packet)

        if not require_response:
            return

        assert transmission_id not in self.pending_results
        async_result = AsyncResult()
        self.pending_results[transmission_id] = async_result, response_class
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

    def connect(self, host, port, timeout=None, ignore_heartbeat=False):
        sock = socket.create_connection((host, port), timeout=timeout)
        conn = self.new_connection(sock, False, ignore_heartbeat)
        return conn

    def listen(self, host, port, backlog=1024):
        self._setup_server()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(backlog)
        sock.setblocking(0)
        accept_watcher = self.loop.io(sock.fileno(), READ, priority=MAXPRI)
        accept_watcher.start(self._do_accept, sock)

    def new_connection(self, sock, server_side, ignore_heartbeat=False):
        conn = Connection(sock, server_side)
        #print 'new_connection', conn.conn_id
        if server_side:
            assert conn.conn_id not in self._income_connections
            self._income_connections[conn.conn_id] = conn
        else:
            assert conn.conn_id not in self._outcome_connections
            self._outcome_connections[conn.conn_id] = conn

        conn.set_close_cb(self.connection_closed)
        conn.gr = greenlet_pool.spawn(self._handle_loop, conn)
        self._setup_heartbeat(conn, server_side, ignore_heartbeat)
        return conn

    def connection_closed(self, conn, reason=None):
        #print 'connection_closed', (conn.conn_id, reason)
        conn.gr.kill(block=False)
        if conn.server_side:
            assert conn.conn_id in self._income_connections
            del self._income_connections[conn.conn_id]
        else:
            assert conn.conn_id in self._outcome_connections
            del self._outcome_connections[conn.conn_id]
        # TODO: clean pending_results if needed
        #del self.pending_results[transmission_id]

    def serve_forever(self):
        wait()

    @property
    def is_full(self):
        return len(self._income_connections) >= self.MAX_CONCURRENCY

    def _setup_server(self):
        # only server need monitor service
        monitor_service = MonitorServiceImpl()
        monitor_service.channel = self
        self.append_service(monitor_service)

    def _setup_heartbeat(self, conn, server_side, ignore_heartbeat):
        if server_side:
            if self.need_heartbeat:
                conn.setup_server_heartbeat(
                    self.heartbeat_interval, self.max_heartbeat_timeout_count
                )
        elif not ignore_heartbeat:
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
                self.logger.exception(ex)
                raise
            self.new_connection(client_socket, server_side=True)

    def _handle_loop(self, conn):
        send, recv, reason, controller = conn.send, conn.recv, None, Controller()
        recv_request, recv_response = self._recv_request, self._recv_response
        meta_data, controller.conn = controller.meta_data, conn

        def send_back(response):
            assert response, 'rpc does not require a response of None'
            meta_data.message = response.SerializeToString()
            send(meta_data.SerializeToString())

        try:
            while 1:
                packet = recv()
                if not packet:
                    break
                controller.Reset()
                meta_data.ParseFromString(packet)
                if meta_data.from_stub: # request
                    try:
                        recv_request(controller, send_back)
                    except BaseError as ex:
                        controller.SetFailed(ex)
                        send(meta_data.SerializeToString())
                else:
                    recv_response(controller)
        except Exception as ex:
            reason = ex
        finally:
            controller.conn = None
            conn.close(reason)

    def _recv_request(self, controller, send_back):
        meta_data = controller.meta_data
        meta_data.from_stub = False
        service = self.services.get(meta_data.service_name, None)

        if service is None:
            raise ServiceNotExist(service_name=meta_data.service_name)

        method = service.DESCRIPTOR.FindMethodByName(meta_data.method_name)
        if method is None:
            raise MethodNotExist(service_name=meta_data.service_name,
                                 method_name=meta_data.method_name)

        request_class = service.GetRequestClass(method)
        request = request_class()
        request.ParseFromString(meta_data.message)
        service.CallMethod(method, controller, request, send_back)

    def _recv_response(self, controller):
        transmission_id = controller.meta_data.transmission_id
        assert transmission_id in self.pending_results
        async_result, response_class = self.pending_results.pop(transmission_id)

        if controller.Failed():
            error_message = ErrorMessage()
            error_message.ParseFromString(controller.meta_data.message)
            cls = BaseMeta.get_by_code(error_message.error_code)
            ex = cls()
            ex.message = error_message.error_message
            async_result.set_exception(ex)
            return

        response = response_class()
        try:
            response.ParseFromString(controller.meta_data.message)
        except DecodeError as ex:
            async_result.set_exception(ex)
        else:
            async_result.set(response)
