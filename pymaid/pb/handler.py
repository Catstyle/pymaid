from _socket import error as socket_error

from gevent.queue import Queue

from pymaid.conf import settings
from pymaid.error import RpcError
from pymaid.utils import greenlet_pool

from . import unpack_header
from .controller import Controller
from .listener import Listener
from .pymaid_pb2 import Controller as PBC


class PBHandler(object):

    def __init__(self, listener=None, close_conn_onerror=True):
        self.listener = listener or Listener()
        self.close_conn_onerror = close_conn_onerror

    def __call__(self, conn):
        conn.close_conn_onerror = self.close_conn_onerror

        RESPONSE = PBC.RESPONSE
        callbacks = {
            PBC.REQUEST: self.listener.handle_request,
            PBC.NOTIFICATION: self.listener.handle_notification,
        }
        handle_response = self.listener.handle_response
        try:
            if not conn.oninit():
                return
            while 1:
                header = conn.read(4)
                if not header:
                    conn.close(reset=True)
                    break
                packet_length, content_length = unpack_header(header)
                if packet_length + content_length > settings.MAX_PACKET_LENGTH:
                    conn.close(RpcError.PacketTooLarge(
                        packet_length + content_length
                    ))
                    break

                buf = conn.read(packet_length + content_length)
                meta = PBC.FromString(buf[:packet_length])
                controller = Controller(meta, conn)
                content = buf[packet_length:]
                controller.header_buf = header

                packet_type = meta.packet_type
                if packet_type == RESPONSE:
                    handle_response(controller, content)
                else:
                    callbacks[packet_type](controller, content)
        except socket_error as ex:
            conn.close(ex, reset=True)
        except Exception as ex:
            conn.close(ex)


class PBHandlerWithWorker(object):

    def __init__(self, listener=None, close_conn_onerror=True):
        self.listener = listener or Listener()
        self.close_conn_onerror = close_conn_onerror

    def __call__(self, conn):
        if not conn.oninit():
            return
        conn.close_conn_onerror = self.close_conn_onerror

        tasks_queue = Queue(settings.MAX_TASKS)
        new_task = tasks_queue.put
        gr = greenlet_pool.spawn(self.sequential_worker, tasks_queue)
        gr.link_exception(conn.close)

        RESPONSE = PBC.RESPONSE
        callbacks = {
            PBC.REQUEST: self.listener.handle_request,
            PBC.NOTIFICATION: self.listener.handle_notification,
        }
        handle_response = self.listener.handle_response
        try:
            while 1:
                header = conn.read(4)
                if not header:
                    conn.close(reset=True)
                    break
                packet_length, content_length = unpack_header(header)
                if packet_length + content_length > settings.MAX_PACKET_LENGTH:
                    conn.close(RpcError.PacketTooLarge(
                        packet_length + content_length
                    ))
                    break

                buf = conn.read(packet_length + content_length)
                meta = PBC.FromString(buf[:packet_length])
                controller = Controller(meta, conn)
                content = buf[packet_length:]
                controller.header_buf = header

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
