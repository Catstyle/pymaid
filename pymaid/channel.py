__all__ = ['Channel']

import time

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
from pymaid.utils import greenlet_pool, pymaid_logger_wrapper
from pymaid.pb.pymaid_pb2 import Void, ErrorMessage


@pymaid_logger_wrapper
class Channel(RpcChannel):

    # Sets the maximum number of consecutive accepts that a process may perform
    # on a single wake up. High values give higher priority to high connection
    # rates, while lower values give higher priority to already established
    # connections.
    # Default is 256. Note, that in case of multiple working processes on the
    # same listening value, it should be set to a lower value.
    # (pywsgi.WSGIServer sets it to 1 when environ["wsgi.multiprocess"] is true)
    MAX_ACCEPT = 256
    MAX_CONCURRENCY = 50000

    def __init__(self, loop=None):
        super(Channel, self).__init__()

        self.loop = loop or get_hub().loop

        self._income_connections = {}
        self._outcome_connections = {}
        self.services = {}
        self.service_method = {}
        self.request_response = {}
        self.stub_response = {}

        self.need_heartbeat = False
        self.heartbeat_interval = 0
        self.max_heartbeat_timeout_count = 0

        self._notify_heartbeat_connections = []
        self._server_heartbeat_timer = self.loop.timer(0, 1, priority=MAXPRI-1)
        self._peer_heartbeat_timer = self.loop.timer(0, 1, priority=MAXPRI)

    def CallMethod(self, method, controller, request, response_class, callback):
        meta_data = controller.meta_data
        meta_data.from_stub = True
        meta_data.service_name = method.containing_service.full_name
        meta_data.method_name = method.name
        if not isinstance(request, Void):
            meta_data.message = request.SerializeToString()

        require_response = not issubclass(response_class, Void)
        if require_response:
            transmission_id = controller.conn.transmission_id
            controller.conn.transmission_id += 1
            meta_data.transmission_id = transmission_id

        packet = meta_data.SerializeToString()
        if controller.broadcast:
            # broadcast
            assert not require_response
            for conn in self._income_connections.itervalues():
                conn.send(packet)
        elif controller.group:
            # small broadcast
            assert not require_response
            get_conn = self.get_income_connection
            for conn_id in controller.group:
                conn = get_conn(conn_id)
                if conn:
                    conn.send(packet)
        else:
            controller.conn.send(packet)

        if not require_response:
            return

        service_method = meta_data.service_name + meta_data.method_name
        self.stub_response.setdefault(service_method, response_class)
        async_result = AsyncResult()
        controller.conn.transmissions[transmission_id] = async_result
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
        self._server_heartbeat_timer.again(self._server_heartbeat, update=True)
        # TODO: enable all connections heartbeat?

    def disable_heartbeat(self):
        self.need_heartbeat = False
        self.heartbeat_interval = 0
        self.max_heartbeat_timeout_count = 0
        self._server_heartbeat_timer.stop()

    def get_income_connection(self, conn_id):
        return self._income_connections.get(conn_id)
    
    def get_outcome_connection(self, conn_id):
        return self._outcome_connections.get(conn_id)

    def connect(self, host, port, timeout=None, ignore_heartbeat=False):
        sock = socket.create_connection((host, port), timeout=timeout)
        conn = self.new_connection(sock, False, ignore_heartbeat)
        if not self._peer_heartbeat_timer.active:
            self._peer_heartbeat_timer.again(self._peer_heartbeat, update=False)
        return conn

    def listen(self, host, port, backlog=MAX_ACCEPT*2):
        self._setup_server()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(backlog)
        sock.setblocking(0)
        accept_watcher = self.loop.io(sock.fileno(), READ, priority=MAXPRI)
        accept_watcher.start(self._do_accept, sock)

    def new_connection(self, sock, server_side, ignore_heartbeat=False):
        conn = Connection(self.loop, sock, server_side)
        conn.set_close_cb(self.connection_closed)
        greenlet_pool.spawn(self.handle_cb, conn)
        self._setup_heartbeat(conn, server_side, ignore_heartbeat)

        if server_side:
            assert conn.conn_id not in self._income_connections
            self._income_connections[conn.conn_id] = conn
        else:
            assert conn.conn_id not in self._outcome_connections
            self._outcome_connections[conn.conn_id] = conn
        self.logger.debug(
            '[Connection|%d][host|%s][peer|%s] made',
            conn.conn_id, conn.sockname, conn.peername
        )
        return conn

    def connection_closed(self, conn, reason=None):
        conn_id = conn.conn_id
        if conn.server_side:
            assert conn_id in self._income_connections, conn_id
            del self._income_connections[conn_id]
        else:
            assert conn_id in self._outcome_connections, conn_id
            del self._outcome_connections[conn_id]
        for async_result in conn.transmissions.itervalues():
            # we should not reach here with async_result left
            # that should be an exception
            async_result.set_exception(reason)
        conn.transmissions.clear()
        if conn.need_heartbeat:
            assert conn_id in self._notify_heartbeat_connections
            del self._notify_heartbeat_connections[conn_id]

    def serve_forever(self):
        wait()

    @property
    def is_full(self):
        return len(self._income_connections) >= self.MAX_CONCURRENCY

    @property
    def size(self):
        return len(self._income_connections) + len(self._outcome_connections)

    def _setup_server(self):
        # only server need monitor service
        monitor_service = MonitorServiceImpl()
        monitor_service.channel = self
        self.append_service(monitor_service)

    def add_notify_heartbeat_conn(self, conn_id):
        self._notify_heartbeat_connections.append(conn_id)

    def _setup_heartbeat(self, conn, server_side, ignore_heartbeat):
        if server_side:
            if self.need_heartbeat:
                conn.setup_server_heartbeat(self.max_heartbeat_timeout_count)
        elif not ignore_heartbeat:
            conn.setup_client_heartbeat(channel=self)

    def _server_heartbeat(self):
        # network delay compensation
        now, server_interval = time.time(), self.heartbeat_interval * 1.1 + .3
        connections = self._income_connections
        for conn_id in connections.keys():
            conn = connections[conn_id]
            if now - conn.last_check_heartbeat >= server_interval:
                conn.last_check_heartbeat = now
                conn.heartbeat_timeout()
        self.logger.debug(
            '[server_heartbeat][escaped|%f] loop done', time.time() - now
        )
        self._server_heartbeat_timer.again(self._server_heartbeat)

    def _peer_heartbeat(self):
        now = time.time()
        # event iteration compensation
        factor = self.size >= 14142 and .64 or .89
        connections = self._outcome_connections
        for conn_id in self._notify_heartbeat_connections:
            conn = connections[conn_id]
            if not conn.need_heartbeat:
                continue
            if now - conn.last_check_heartbeat >= conn.heartbeat_interval * factor:
                conn.last_check_heartbeat = now
                conn.notify_heartbeat()
        self.logger.debug(
            '[peer_heartbeat][escaped|%f] loop done', time.time() - now
        )
        self._peer_heartbeat_timer.again(self._peer_heartbeat)

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

    def get_service_method(self, meta):
        service_name, method_name = meta.service_name, meta.method_name
        service_method = service_name + method_name
        if service_method in self.service_method:
            return self.service_method[service_method]

        if service_name not in self.services:
            raise ServiceNotExist(service_name=service_name)

        service = self.services[service_name]
        method = service.DESCRIPTOR.FindMethodByName(method_name)
        if not method:
            raise MethodNotExist(service_name=service_name, method_name=method_name)

        request_class = service.GetRequestClass(method)
        response_class = service.GetResponseClass(method)
        self.service_method[service_method] = service, method
        self.request_response[service_method] = request_class, response_class
        return service, method

    def get_request_response(self, meta):
        service_name, method_name = meta.service_name, meta.method_name
        service_method = service_name + method_name
        if service_method not in self.request_response:
            self.get_service_method(meta)
        return self.request_response[service_method]

    def get_stub_response_class(self, meta):
        return self.stub_response[meta.service_name + meta.method_name]

    def handle_cb(self, conn):
        recv, reason, controller = conn.recv, None, Controller()
        handle_request, handle_response = self.handle_request, self.handle_response
        handle_notification = self.handle_notification
        meta_data, controller.conn = controller.meta_data, conn
        try:
            while 1:
                packet = recv()
                if not packet:
                    break
                controller.Reset()
                meta_data.ParseFromString(packet)
                if meta_data.from_stub: # request
                    if meta_data.is_notification:
                        handle_notification(conn, controller)
                    else:
                        handle_request(conn, controller)
                else:
                    handle_response(conn, controller)
        except Exception as ex:
            reason = ex
        finally:
            conn.close(reason)

    def handle_request(self, conn, controller):
        meta_data = controller.meta_data
        meta_data.from_stub = False

        try:
            service, method = self.get_service_method(meta_data)
        except (ServiceNotExist, MethodNotExist) as ex:
            controller.SetFailed(ex)
            conn.send(meta_data.SerializeToString())
            return

        request_class, response_class = self.get_request_response(meta_data)
        def send_response(response):
            # received broadcast, just ignore the unwanted response
            # just in case, it may be error
            if response_class is Void:
                return
            assert response, 'rpc does not require a response of None'
            assert isinstance(response, response_class)
            meta_data.message = response.SerializeToString()
            conn.send(meta_data.SerializeToString())

        request = request_class()
        request.ParseFromString(meta_data.message)
        try:
            service.CallMethod(method, controller, request, send_response)
        except BaseError as ex:
            controller.SetFailed(ex)
            conn.send(meta_data.SerializeToString())

    def handle_notification(self, conn, controller):
        meta_data = controller.meta_data
        try:
            service, method = self.get_service_method(meta_data)
        except (ServiceNotExist, MethodNotExist):
            # failed silently when handle_notification
            return

        request_class, response_class = self.get_request_response(meta_data)
        request = request_class()
        request.ParseFromString(meta_data.message)
        try:
            service.CallMethod(method, controller, request, None)
        except BaseError:
            # failed silently when handle_notification
            pass

    def handle_response(self, conn, controller):
        transmission_id = controller.meta_data.transmission_id
        assert transmission_id in conn.transmissions
        async_result = conn.transmissions.pop(transmission_id)

        if controller.Failed():
            error_message = ErrorMessage()
            error_message.ParseFromString(controller.meta_data.message)
            ex = BaseMeta.get_by_code(error_message.error_code)()
            ex.message = error_message.error_message
            async_result.set_exception(ex)
        else:
            response = self.get_stub_response_class(controller.meta_data)()
            try:
                response.ParseFromString(controller.meta_data.message)
            except DecodeError as ex:
                async_result.set_exception(ex)
            else:
                async_result.set(response)
