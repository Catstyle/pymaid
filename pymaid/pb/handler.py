from _socket import error as socket_error

from gevent.queue import Queue
from google.protobuf.message import DecodeError

from pymaid.error import RpcError, get_ex_by_code
from pymaid.error.base import BaseEx, Error
from pymaid.utils import greenlet_pool
from pymaid.parser import HEADER_LENGTH, pack, unpack_packet, unpack_header

from pymaid.pb.controller import Controller
from pymaid.pb.listener import Listener
from pymaid.pb.stub import StubManager
from pymaid.pb.pymaid_pb2 import Void, ErrorMessage, Controller as PBC

REQUEST, RESPONSE, NOTIFICATION = PBC.REQUEST, PBC.RESPONSE, PBC.NOTIFICATION
RPCNotExist, PacketTooLarge = RpcError.RPCNotExist, RpcError.PacketTooLarge


class PBHandler(object):

    MAX_PACKET_LENGTH = 8 * 1024

    def __init__(self, conn, listener=None, close_conn_onerror=True):
        self.listener = listener or Listener()
        self.close_conn_onerror = close_conn_onerror
        self._get_rpc = self.listener.service_methods.get
        self.run(conn)

    def run(self, conn):
        if not conn.oninit():
            return
        header_length, max_packet_length = HEADER_LENGTH, self.MAX_PACKET_LENGTH
        read = conn.read
        tasks_queue, handle_response = Queue(), self.handle_response
        gr = greenlet_pool.spawn(self.sequential_worker, tasks_queue)
        gr.link_exception(conn.close)

        callbacks = {
            REQUEST: self.handle_request,
            NOTIFICATION: self.handle_notification,
        }
        new_task = tasks_queue.put
        try:
            while 1:
                header = read(header_length)
                if not header:
                    conn.close(reset=True)
                    break
                parser_type, packet_length, content_length = unpack_header(header)
                if packet_length > max_packet_length:
                    conn.close(PacketTooLarge(packet_length=packet_length))
                    break

                buf = read(packet_length+content_length)
                meta = unpack_packet(buf[:packet_length], PBC, parser_type)
                controller = Controller(meta, conn, parser_type)
                content = buf[packet_length:]
                packet_type = meta.packet_type
                if packet_type == RESPONSE:
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
        meta.packet_type = RESPONSE
        service_method = meta.service_method

        conn, parser_type = controller.conn, controller.parser_type
        rpc = self._get_rpc(service_method)
        if not rpc:
            meta.is_failed = True
            err = RPCNotExist(service_method=service_method)
            err = ErrorMessage(error_code=err.code, error_message=err.message)
            conn.send(pack(meta, err, parser_type))
            return

        method, request_class, response_class = rpc
        def send_response(response=None, **kwargs):
            if response_class is Void:
                # do not send_response when response_class is Void
                return
            if response is None:
                response = response_class(**kwargs)
            assert isinstance(response, response_class)
            conn.send(pack(meta, response, parser_type))

        request = unpack_packet(content, request_class, parser_type)
        try:
            method(controller, request, send_response)
        except BaseEx as ex:
            meta.is_failed = True
            err = ErrorMessage(error_code=ex.code, error_message=ex.message)
            conn.send(pack(meta, err, parser_type))
            if isinstance(ex, Error) and self.close_conn_onerror:
                conn.delay_close(ex)

    def handle_notification(self, controller, content):
        service_method = controller.meta.service_method
        rpc = self._get_rpc(service_method)
        if not rpc:
            # failed silently when handle_notification
            return

        method, request_class, response_class = rpc
        request = unpack_packet(content, request_class, controller.parser_type)
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

        parser_type = controller.parser_type
        if meta.is_failed:
            error_message = unpack_packet(content, ErrorMessage, parser_type)
            ex = get_ex_by_code(error_message.error_code)()
            ex.message = error_message.error_message
            async_result.set_exception(ex)
        else:
            response_cls = StubManager.response_class[meta.service_method]
            try:
                async_result.set(
                    unpack_packet(content, response_cls, parser_type)
                )
            except DecodeError as ex:
                async_result.set_exception(ex)
