import struct
from _socket import error as socket_error

from gevent.queue import Queue
from google.protobuf.message import DecodeError

from pymaid.conf import settings
from pymaid.error import BaseEx, Error, RpcError
from pymaid.error import get_exception
from pymaid.utils import greenlet_pool

from .controller import Controller
from .listener import Listener
from .stub import StubManager
from .pymaid_pb2 import Void, ErrorMessage, Controller as PBC


class PBHandler(object):

    HEADER = '!HH'
    header_length = struct.calcsize(HEADER)
    header_struct = struct.Struct(HEADER)
    pack_header = header_struct.pack
    unpack_header = header_struct.unpack

    def __init__(self, listener=None, close_conn_onerror=True):
        self.listener = listener or Listener()
        self.close_conn_onerror = close_conn_onerror
        self._get_rpc = self.listener.service_methods.get

    def __call__(self, conn):
        if not conn.oninit():
            return

        tasks_queue = Queue(settings.MAX_TASKS)
        new_task = tasks_queue.put
        gr = greenlet_pool.spawn(self.sequential_worker, tasks_queue)
        gr.link_exception(conn.close)

        header_length = self.header_length
        RESPONSE = PBC.RESPONSE
        callbacks = {
            PBC.REQUEST: self.handle_request,
            PBC.NOTIFICATION: self.handle_notification,
        }
        handle_response = self.handle_response
        try:
            while 1:
                header = conn.read(header_length)
                if not header:
                    conn.close(reset=True)
                    break
                packet_length, content_length = self.unpack_header(header)
                if packet_length + content_length > settings.MAX_PACKET_LENGTH:
                    conn.close(RpcError.PacketTooLarge(
                        packet_length=packet_length + content_length
                    ))
                    break

                buf = conn.read(packet_length + content_length)
                meta = PBC.FromString(buf[:packet_length])
                controller = Controller(meta, conn)
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
            gr.kill(block=False)

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
            packet = ErrorMessage(code=err.code, message=err.message)
            conn.send(b'{}{}{}'.format(
                self.pack_header(meta.ByteSize(), packet.ByteSize()),
                meta.SerializeToString(), packet.SerializeToString()
            ))
            return

        method, request_class, response_class = rpc

        def send_response(response=None, **kwargs):
            if response_class is Void:
                # do not send_response when response_class is Void
                return
            packet = response or response_class(**kwargs)
            conn.send(b'{}{}{}'.format(
                self.pack_header(meta.ByteSize(), packet.ByteSize()),
                meta.SerializeToString(), packet.SerializeToString()
            ))

        request = request_class.FromString(content)
        try:
            method(controller, request, send_response)
        except BaseEx as ex:
            meta.is_failed = True
            packet = ErrorMessage(code=ex.code, message=ex.message)
            conn.send(b'{}{}{}'.format(
                self.pack_header(meta.ByteSize(), packet.ByteSize()),
                meta.SerializeToString(), packet.SerializeToString()
            ))
            if isinstance(ex, Error) and self.close_conn_onerror:
                conn.delay_close(ex)

    def handle_notification(self, controller, content):
        service_method = controller.meta.service_method
        rpc = self._get_rpc(service_method)
        if not rpc:
            # failed silently when handle_notification
            return

        method, request_class, response_class = rpc
        request = request_class.FromString(content)
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
                message = ErrorMessage.FromString(content)
                ex = get_exception(message.code, message.message)
            except (DecodeError, ValueError) as ex:
                ex = ex
            async_result.set_exception(ex)
        else:
            response_cls = StubManager.response_class[meta.service_method]
            try:
                async_result.set(response_cls.FromString(content))
            except (DecodeError, ValueError) as ex:
                async_result.set_exception(ex)
