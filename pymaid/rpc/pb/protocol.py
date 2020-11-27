from queue import deque
from struct import Struct
from typing import Optional, Sequence, Tuple, Union

from google.protobuf.message import Message
from orjson import dumps

from pymaid.conf import settings
from pymaid.core import create_task, Event
from pymaid.error import BaseEx
from pymaid.net import DataType, Protocol
from pymaid.rpc.method import ServiceRepository
from pymaid.rpc.pymaid_pb2 import Controller as Meta, ErrorMessage
from pymaid.utils.logger import logger_wrapper

from .error import PBError

st = Struct(settings.get('PM_PB_HEADER', ns='pymaid'))
header_size = st.size
pack_header = st.pack
unpack_header = st.unpack


@logger_wrapper
class Handler:

    def __init__(
        self,
        service_repository: ServiceRepository,
        timeout: Optional[float] = None,
    ):
        self.service_repository = service_repository
        self.timeout = timeout

        self.messages = deque()
        self.message_received = Event()
        self.is_closing = False
        self.is_closed = False

        self.callbacks = {
            Meta.PacketType.REQUEST: self.handle_request,
            Meta.PacketType.RESPONSE: self.handle_response,
        }

        self.task = create_task(self.run())
        self.task.add_done_callback(self.task_done)

    async def run(self):
        while 1:
            await self.message_received.wait()
            while len(self.messages):
                message = self.messages.popleft()
                if not message:
                    return
                meta, payload = message
                # if callback for packet_type not exists, just let it crash
                try:
                    await self.callbacks[meta.packet_type](meta, payload)
                except BaseEx as exc:
                    meta.is_failed = True
                    packet = ErrorMessage(code=exc.code, message=exc.message),
                    if exc.data:
                        packet.data = dumps(exc.data)
                    self.conn.send_message(meta, packet)
                except Exception as exc:
                    self.close(exc)
                    return
            self.message_received.clear()

    async def join(self):
        if self.is_closing:
            return
        self.is_closing = True
        self.messages.append(None)
        self.message_received.set()
        await self.task
        self.close()

    def close(self, exc: Optional[Union[str, Exception]] = None, join=True):
        if self.is_closed:
            return
        self.is_closed = True
        # maybe called from run loop
        if join:
            self.is_closing = True
            self.messages.append(None)
            self.message_received.set()

    def task_done(self, task):
        self.messages.clear()
        self.conn.close()
        self.conn = None
        del self.callbacks

    def feed_message(self, messages):
        self.messages.extend(messages)
        self.message_received.set()

    async def handle_request(self, meta, payload):
        name = meta.service_method
        if (rpc := self.service_repository.get_service_method(name)) is None:
            raise PBError.RPCNotFound(data={'name': name})
        await rpc(meta, payload, conn=self.conn, timeout=self.timeout)

    async def handle_response(self, meta, payload):
        if (controller := self.conn.get_controller(meta.transmission_id)) is None:
            # invalid transmission_id, do nothing
            self.logger.warning(f'{self.conn} received invalid response, {meta.transmission_id=}')
            return
        controller.feed_message(meta, payload)


class Protocol(Protocol):

    def feed_data(self, data: DataType) -> Sequence[Message]:
        data = memoryview(data)
        messages = []

        used_size = 0
        max_packet = settings.get('MAX_PACKET_LENGTH', ns='pymaid')
        try:
            while 1:
                consumed, meta, payload = self.decode(data, max_packet)
                if not consumed:
                    break
                assert meta
                messages.append((meta, payload))
                used_size += consumed
                data = data[consumed:]
        finally:
            data.release()

        return used_size, messages

    def encode(self, meta: Meta, message: Message) -> bytes:
        meta.payload_size = message.ByteSize()
        return (
            pack_header(meta.ByteSize())
            + meta.SerializeToString()
            + message.SerializeToString()
        )

    def decode(self, data: memoryview, max_packet: int) -> Tuple[int, Meta, memoryview]:
        nbytes = data.nbytes
        if nbytes < header_size:
            return 0, None, None

        needed_size = header_size
        meta_size = unpack_header(data[:needed_size])[0]
        needed_size += meta_size
        if nbytes < needed_size:
            return 0, None, None

        meta = Meta.FromString(data[header_size:needed_size])
        if meta.payload_size > max_packet:
            raise PBError.PacketTooLarge(
                data={'max': max_packet, 'size': meta.payload_size}
            )
        needed_size += meta.payload_size

        return needed_size, meta, data[header_size + meta_size: needed_size]
