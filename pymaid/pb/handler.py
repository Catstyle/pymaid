from _socket import error as socket_error

from gevent.queue import Queue
from google.protobuf.message import DecodeError

from pymaid.error import BaseEx, Error, RpcError, InvalidErrorMessage
from pymaid.error import get_ex_by_code
from pymaid.utils import greenlet_pool
from pymaid.parser import HEADER_LENGTH, unpack_header

from pymaid.pb.controller import Controller
from pymaid.pb.listener import Listener
from pymaid.pb.stub import StubManager
from pymaid.pb.pymaid_pb2 import Void, ErrorMessage, Controller as PBC


class PBHandler(object):

    MAX_PACKET_LENGTH = 8 * 1024
    MAX_TASKS = 64

    def __init__(self, conn, parser, listener=None, close_conn_onerror=True):
        self.listener = listener or Listener()
        self.close_conn_onerror = close_conn_onerror
        self.pack_meta, self.unpack = parser.pack_meta, parser.unpack
        self._get_rpc = self.listener.service_methods.get
        self.run(conn)

    def run(self, conn):
        if not conn.oninit():
            return
        header_length = HEADER_LENGTH
        max_packet_length = self.MAX_PACKET_LENGTH
        read, unpack = conn.read, self.unpack
        tasks_queue = Queue(self.MAX_TASKS)
        handle_response = self.handle_response
        gr = greenlet_pool.spawn(self.sequential_worker, tasks_queue)
        gr.link_exception(conn.close)

        callbacks = {
            PBC.REQUEST: self.handle_request,
            PBC.NOTIFICATION: self.handle_notification,
        }
        response, new_task = PBC.RESPONSE, tasks_queue.put
        try:
            while 1:
                header = read(header_length)
                if not header:
                    conn.close(reset=True)
                    break
                packet_length, content_length = unpack_header(header)
                if packet_length > max_packet_length:
                    conn.close(
                        RpcError.PacketTooLarge(packet_length=packet_length)
                    )
                    break

                buf = read(packet_length + content_length)
                meta = unpack(buf[:packet_length], PBC)
                controller = Controller(meta, conn)
                content = buf[packet_length:]
                packet_type = meta.packet_type
                if packet_type == response:
                    handle_response(controller, content)
                else:
                    new_task((callbacks[packet_type], controller, content))
        except socket_error as ex:
            conn.close(ex, reset=True)
        except Exception as ex:
            conn.close(ex)
        finally:
            tasks_queue.queue.clear()
            new_task(None)

    def sequential_worker(self, tasks_queue):
        get_task = tasks_queue.get
        while 1:
            task = get_task()
            if not task:
                break
            callback, controller, content = task
            callback(controller, content)

    def handle_request(self, controller, content):
        meta = controller.meta
        meta.packet_type = PBC.RESPONSE
        service_method = meta.service_method

        conn = controller.conn
        rpc = self._get_rpc(service_method)
        if not rpc:
            meta.is_failed = True
            err = RpcError.RPCNotExist(service_method=service_method)
            err = ErrorMessage(error_code=err.code, error_message=err.message)
            conn.send(self.pack_meta(meta, err))
            return

        method, request_class, response_class = rpc

        def send_response(response=None, **kwargs):
            if response_class is Void:
                # do not send_response when response_class is Void
                return
            if response is None:
                response = response_class(**kwargs)
            assert isinstance(response, response_class), \
                (type(response), response_class)
            conn.send(self.pack_meta(meta, response))

        request = self.unpack(content, request_class)
        try:
            method(controller, request, send_response)
        except BaseEx as ex:
            meta.is_failed = True
            err = ErrorMessage(error_code=ex.code, error_message=ex.message)
            conn.send(self.pack_meta(meta, err))
            if isinstance(ex, Error) and self.close_conn_onerror:
                conn.delay_close(ex)

    def handle_notification(self, controller, content):
        service_method = controller.meta.service_method
        rpc = self._get_rpc(service_method)
        if not rpc:
            # failed silently when handle_notification
            return

        method, request_class, response_class = rpc
        request = self.unpack(content, request_class)
        try:
            method(controller, request, lambda *args, **kwargs: '')
        except BaseEx:
            # failed silently when handle_notification
            pass

    def handle_response(self, controller, content):
        conn, meta = controller.conn, controller.meta
        transmission_id = meta.transmission_id
        async_result = conn.transmissions.pop(transmission_id, None)
        if not async_result:
            # invalid transmission_id, do nothing
            return

        if meta.is_failed:
            try:
                error_message = self.unpack(content, ErrorMessage)
                ex = get_ex_by_code(error_message.error_code)()
                ex.message = error_message.error_message
            except (DecodeError, ValueError, InvalidErrorMessage) as ex:
                ex = ex
            async_result.set_exception(ex)
        else:
            response_cls = StubManager.response_class[meta.service_method]
            try:
                async_result.set(self.unpack(content, response_cls))
            except (DecodeError, ValueError) as ex:
                async_result.set_exception(ex)
