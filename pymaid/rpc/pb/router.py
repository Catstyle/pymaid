from orjson import dumps

from google.protobuf.descriptor_pb2 import MethodDescriptorProto
from google.protobuf.service_reflection import GeneratedServiceType

from pymaid.rpc.method import UnaryUnaryMethod, UnaryStreamMethod
from pymaid.rpc.method import StreamUnaryMethod, StreamStreamMethod
from pymaid.rpc.method import UnaryUnaryMethodStub, UnaryStreamMethodStub
from pymaid.rpc.method import StreamUnaryMethodStub, StreamStreamMethodStub
from pymaid.rpc.router import Router, RouterStub

from .error import PBError
from .pymaid_pb2 import Context as Meta, Void, ErrorMessage


class PBRouter(Router):

    def get_service_methods(self, service: GeneratedServiceType):
        for method in service.DESCRIPTOR.methods:
            method_impl = getattr(service, method.name)
            if '.<lambda>' in str(method_impl):
                continue

            mdp = MethodDescriptorProto()
            method.CopyToProto(mdp)
            if not mdp.client_streaming and not mdp.server_streaming:
                method_class = UnaryUnaryMethod
            elif not mdp.client_streaming:
                method_class = UnaryStreamMethod
            elif not mdp.server_streaming:
                method_class = StreamUnaryMethod
            else:
                method_class = StreamStreamMethod
            request_class = service.GetRequestClass(method)
            response_class = service.GetResponseClass(method)
            yield method_class(
                method.name,
                method.full_name,
                method_impl,
                request_class,
                response_class,
                options={
                    'flags': Meta.PacketFlag.NULL,
                    'void_request': issubclass(request_class, Void),
                    'void_response': issubclass(response_class, Void),
                },
            )

    def feed_messages(self, conn, messages):
        Request = Meta.PacketType.REQUEST
        Response = Meta.PacketType.RESPONSE
        get_route = self.get_route
        tasks = []
        for message in messages:
            # check exist context here for a shortcut
            # because just feed message into context won't block,
            # and it makes serial streaming posible
            meta, payload = message
            # self.logger.debug(f'{self} feed meta={meta}')
            if meta.transmission_id in conn.context_manager.contexts:
                conn.context_manager.contexts[meta.transmission_id] \
                    .feed_message(meta, payload)
                continue

            if meta.packet_type == Request:
                name = meta.service_method
                rpc = get_route(name)
                if rpc is None:
                    task = self.handle_error(
                        meta, PBError.RPCNotFound(data={'name': name})
                    )
                else:
                    context = conn.context_manager.new_inbound_context(
                        meta.transmission_id,
                        method=rpc,
                        conn=conn,
                        timeout=conn.timeout,
                    )
                    context.feed_message(meta, payload)
                    task = context.run()
            elif meta.packet_type == Response:
                # response should be handled above as existed context
                self.logger.warning(
                    f'{self!r} received unknown response, '
                    f'id={meta.transmission_id}, ignored.'
                )
                continue
            else:
                task = self.handle_error(
                    conn,
                    meta,
                    PBError.InvalidPacketType(
                        data={'packet_type': meta.packet_type}
                    )
                )
            tasks.append(task)
        return tasks

    async def handle_error(self, conn, meta, error):
        meta.is_failed = True
        meta.packet_type = Meta.PacketType.RESPONSE
        packet = ErrorMessage(code=error.code, message=error.message)
        if error.data:
            packet.data = dumps(error.data)
        await conn.send_message(meta, packet)


class PBRouterStub(RouterStub):

    def get_router_stubs(self, stub):
        for method in stub.DESCRIPTOR.methods:
            mdp = MethodDescriptorProto()
            method.CopyToProto(mdp)
            if not mdp.client_streaming and not mdp.server_streaming:
                method_class = UnaryUnaryMethodStub
            elif not mdp.client_streaming:
                method_class = UnaryStreamMethodStub
            elif not mdp.server_streaming:
                method_class = StreamUnaryMethodStub
            else:
                method_class = StreamStreamMethodStub
            request_class = stub.GetRequestClass(method)
            response_class = stub.GetResponseClass(method)
            yield method_class(
                method.name,
                method.full_name,
                request_class,
                response_class,
                options={
                    'flags': Meta.PacketFlag.NULL,
                    'void_request': issubclass(request_class, Void),
                    'void_response': issubclass(response_class, Void),
                },
            )
