__all__ = ['Channel']

import time

from gevent.event import AsyncResult
from gevent import socket
from gevent import wait
from gevent.core import READ, MAXPRI
from gevent.hub import get_hub

from google.protobuf.service import RpcChannel

from pymaid.connection import Connection
from pymaid.parser import REQUEST, RESPONSE, NOTIFICATION, pack_packet
from pymaid.agent import ServiceAgent
from pymaid.apps.monitor import MonitorServiceImpl, MonitorService_Stub
from pymaid.error import BaseError, ServiceNotExist, MethodNotExist
from pymaid.utils import pymaid_logger_wrapper
from pymaid.pb.pymaid_pb2 import Void


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

        self.listers = []
        self._had_setup_server = False
        self._income_connections = {}
        self._outcome_connections = {}

        self.services = {}
        self.service_method = {}
        self.request_response = {}
        self.stub_response = {}

        self.monitor_agent = ServiceAgent(MonitorService_Stub(self))
        self.need_heartbeat = False
        self.heartbeat_interval = 0
        self.max_heartbeat_timeout_count = 0

        self._notify_heartbeat_connections = []
        self._server_heartbeat_timer = self.loop.timer(0, 1, priority=MAXPRI-1)
        self._peer_heartbeat_timer = self.loop.timer(0, 1, priority=MAXPRI)

    def _setup_server(self):
        # only server need monitor service
        self._had_setup_server = True
        monitor_service = MonitorServiceImpl()
        monitor_service.channel = self
        self.append_service(monitor_service)

    def _setup_heartbeat(self, conn, server_side, ignore_heartbeat):
        if server_side:
            if self.need_heartbeat:
                conn.setup_server_heartbeat(self.max_heartbeat_timeout_count)
        elif not ignore_heartbeat:
            resp = self.monitor_agent.get_heartbeat_info(conn=conn)
            if resp.need_heartbeat:
                conn.setup_client_heartbeat(resp.heartbeat_interval)
                self._notify_heartbeat_connections.append(conn.conn_id)

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
        notify_heartbeat = self.monitor_agent.notify_heartbeat
        for conn_id in self._notify_heartbeat_connections:
            conn = connections[conn_id]
            if not conn.need_heartbeat:
                continue
            if now - conn.last_check_heartbeat >= conn.heartbeat_interval * factor:
                conn.last_check_heartbeat = now
                notify_heartbeat(conn=conn)
        self.logger.debug(
            '[peer_heartbeat][escaped|%f] loop done', time.time() - now
        )
        self._peer_heartbeat_timer.again(self._peer_heartbeat)

    def _do_accept(self, sock):
        for _ in range(self.MAX_ACCEPT):
            if self.is_full:
                return
            try:
                peer_socket, address = sock.accept()
            except socket.error as ex:
                if ex.args[0] == socket.EWOULDBLOCK:
                    return
                self.logger.exception(ex)
                raise
            self.new_connection(peer_socket, server_side=True)

    def CallMethod(self, method, controller, request, response_class, callback):
        meta = controller.meta
        meta.service_name = method.containing_service.full_name
        meta.method_name = method.name
        if not isinstance(request, Void):
            controller.pack_content(request)

        require_response = not issubclass(response_class, Void)
        if require_response:
            meta.packet_type = REQUEST
            transmission_id = controller.conn.transmission_id
            controller.conn.transmission_id += 1
            meta.transmission_id = transmission_id
        else:
            meta.packet_type = NOTIFICATION

        packet_buffer = controller.pack_packet()
        if controller.broadcast:
            # broadcast
            assert not require_response
            for conn in self._income_connections.values():
                conn.send(packet_buffer)
        elif controller.group:
            # small broadcast
            assert not require_response
            get_conn = self.get_income_connection
            for conn_id in controller.group:
                conn = get_conn(conn_id)
                if conn:
                    conn.send(packet_buffer)
        else:
            controller.conn.send(packet_buffer)

        if not require_response:
            return

        service_method = meta.service_name + meta.method_name
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
        if not self._had_setup_server:
            self._setup_server()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(backlog)
        sock.setblocking(0)
        accept_watcher = self.loop.io(sock.fileno(), READ, priority=MAXPRI)
        accept_watcher.start(self._do_accept, sock)
        self.listers.append((sock, accept_watcher))

    def new_connection(self, sock, server_side, ignore_heartbeat=False):
        conn = Connection(self, sock, server_side)
        conn.set_close_cb(self.connection_closed)
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
            for async_result in conn.transmissions.values():
                # we should not reach here with async_result left
                # that should be an exception
                async_result.set_exception(reason)
            conn.transmissions.clear()
            if conn.need_heartbeat:
                assert conn_id in self._notify_heartbeat_connections, conn_id
                self._notify_heartbeat_connections.remove(conn_id)

    def serve_forever(self):
        wait()

    @property
    def is_full(self):
        return len(self._income_connections) >= self.MAX_CONCURRENCY

    @property
    def size(self):
        return len(self._income_connections) + len(self._outcome_connections)

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

    def handle_request(self, conn, controller):
        meta = controller.meta
        meta.packet_type = RESPONSE

        try:
            service, method = self.get_service_method(meta)
        except (ServiceNotExist, MethodNotExist) as ex:
            controller.SetFailed(ex)
            conn.send(controller.pack_packet())
            return

        request_class, response_class = self.get_request_response(meta)
        def send_response(response):
            assert response, 'rpc does not require a response of None'
            assert isinstance(response, response_class)
            controller.pack_content(response)
            conn.send(controller.pack_packet())

        request = request_class()
        request.ParseFromString(controller.content)
        try:
            service.CallMethod(method, controller, request, send_response)
        except BaseError as ex:
            controller.SetFailed(ex)
            conn.send(controller.pack_packet())

    def handle_notification(self, conn, controller):
        meta = controller.meta
        try:
            service, method = self.get_service_method(meta)
        except (ServiceNotExist, MethodNotExist):
            # failed silently when handle_notification
            return

        request_class, response_class = self.get_request_response(meta)
        request = request_class()
        request.ParseFromString(controller.content)
        try:
            service.CallMethod(method, controller, request, None)
        except BaseError:
            # failed silently when handle_notification
            pass
