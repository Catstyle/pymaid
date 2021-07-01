from orjson import loads, dumps
from pymaid.error import ErrorManager
from pymaid.rpc.error import RPCError
from pymaid.rpc.context import InboundContext, OutboundContext

from .pymaid_pb2 import Context as Meta, ErrorMessage, Void


class PBContext:

    async def handle_error(self, error: Exception):
        await self.conn.send_message(
            Meta(
                transmission_id=self.transmission_id,
                packet_flags=(
                    self.method.options.get('flags', 0) | Meta.PacketFlag.END
                ),
                is_failed=True,
            ),
            ErrorMessage(
                code=error.code,
                message=error.message,
                data=dumps(error.data) if error.data else '',
            ),
        )
        self.sent_end_message = True

    async def shutdown(self):
        await self.conn.send_message(
            Meta(
                transmission_id=self.transmission_id,
                packet_flags=(
                    self.method.options.get('flags', 0) | Meta.PacketFlag.END
                ),
            ),
            Void(),
        )


class PBInboundContext(PBContext, InboundContext):

    def feed_message(self, meta, payload):
        '''Received request from transport layer'''
        assert meta.packet_type == Meta.REQUEST, \
            f'invalid packet_type={meta.packet_type}'
        if self.request_fed_count > 0 and not self.method.client_streaming:
            raise RPCError.MultipleRequestForUnaryMethod(
                data={
                    'service_method': self.method.full_name,
                    'transmission_id': self.transmission_id,
                }
            )
        if payload:
            self.request_queue.append(
                self.method.request_class.FromString(payload)
            )
        if meta.packet_flags & Meta.PacketFlag.END:
            self.request_queue.append(None)
        self.request_fed_count += 1
        if self.waiter and not self.waiter.done():
            self.waiter.set_result(True)

    async def send_message(
        self, response=None, *, end: bool = False, **kwargs
    ):
        '''Send response to transport layer'''
        if self.method.options.get('void_response'):
            # do not send_message when response is void
            return
        if self.response_sent_count > 0 and not self.method.server_streaming:
            raise RPCError.RPCResponseSent(
                data={
                    'service_method': self.method.full_name,
                    'transmission_id': self.transmission_id,
                }
            )
        flags = self.method.options.get('flags', 0)
        if end or not self.method.server_streaming:
            flags |= Meta.PacketFlag.END
            self.sent_end_message = True
        await self.conn.send_message(
            Meta(
                transmission_id=self.transmission_id,
                packet_type=Meta.RESPONSE,
                packet_flags=flags
            ),
            response or self.method.response_class(**kwargs),
        )


class PBOutboundContext(PBContext, OutboundContext):

    def feed_message(self, meta, payload):
        '''Received response from transport layer '''
        assert not meta.packet_type or meta.packet_type == Meta.RESPONSE, \
            f'invalid packet_type={meta.packet_type}'
        if self.response_fed_count > 0 and not self.method.server_streaming:
            raise RPCError.MultipleResponseForUnaryMethod(
                data={
                    'service_method': self.method.full_name,
                    'transmission_id': self.transmission_id,
                }
            )

        if meta.is_failed or meta.is_cancelled:
            assert payload, 'should return error message'
            err = ErrorMessage.FromString(payload)
            ex = ErrorManager.assemble(
                err.code, err.message, err.data and loads(err.data) or {}
            )
            self.response_queue.append(ex)
        elif payload:
            self.response_queue.append(
                self.method.response_class.FromString(payload)
            )
        if meta.packet_flags & Meta.PacketFlag.END:
            self.response_queue.append(None)
        if self.waiter and not self.waiter.done():
            self.waiter.set_result(True)

    async def send_message(self, request=None, *, end: bool = False, **kwargs):
        '''Send request to transport layer'''
        if self.request_sent_count > 0 and not self.method.client_streaming:
            raise RPCError.RPCRequestSent(
                data={
                    'service_method': self.method.full_name,
                    'transmission_id': self.transmission_id,
                }
            )

        flags = self.method.options.get('flags', 0)
        if end or not self.method.client_streaming:
            flags |= Meta.PacketFlag.END
            self.sent_end_message = True
        await self.conn.send_message(
            Meta(
                transmission_id=self.transmission_id,
                service_method=self.method.full_name,
                packet_type=Meta.REQUEST,
                packet_flags=flags,
            ),
            request or self.method.request_class(**kwargs),
        )
