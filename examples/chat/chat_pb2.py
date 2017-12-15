# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: examples/chat/chat.proto

import sys
_b = sys.version_info[0] < 3 and (
    lambda x: x) or (lambda x: x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import service as _service
from google.protobuf import service_reflection
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from pymaid.pb import pymaid_pb2 as pymaid_dot_pb_dot_pymaid__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
    name='examples/chat/chat.proto',
    package='chat',
    syntax='proto3',
    serialized_pb=_b('\n\x18\x65xamples/chat/chat.proto\x12\x04\x63hat\x1a\x16pymaid/pb/pymaid.proto\"\x1a\n\x07Message\x12\x0f\n\x07message\x18\x01 \x01(\t\"\x06\n\x04Resp2\x83\x01\n\x0b\x43hatService\x12#\n\x04Join\x12\x0f.pymaid.pb.Void\x1a\n.chat.Resp\x12)\n\x07Publish\x12\r.chat.Message\x1a\x0f.pymaid.pb.Void\x12$\n\x05Leave\x12\x0f.pymaid.pb.Void\x1a\n.chat.Resp2:\n\rChatBroadcast\x12)\n\x07Publish\x12\r.chat.Message\x1a\x0f.pymaid.pb.VoidB\x03\x90\x01\x01\x62\x06proto3'),
    dependencies=[pymaid_dot_pb_dot_pymaid__pb2.DESCRIPTOR, ])


_MESSAGE = _descriptor.Descriptor(
    name='Message',
    full_name='chat.Message',
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    fields=[
        _descriptor.FieldDescriptor(
            name='message', full_name='chat.Message.message', index=0,
            number=1, type=9, cpp_type=9, label=1,
            has_default_value=False, default_value=_b("").decode('utf-8'),
            message_type=None, enum_type=None, containing_type=None,
            is_extension=False, extension_scope=None,
            options=None, file=DESCRIPTOR),
    ],
    extensions=[
    ],
    nested_types=[],
    enum_types=[
    ],
    options=None,
    is_extendable=False,
    syntax='proto3',
    extension_ranges=[],
    oneofs=[
    ],
    serialized_start=58,
    serialized_end=84,
)


_RESP = _descriptor.Descriptor(
    name='Resp',
    full_name='chat.Resp',
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    fields=[
    ],
    extensions=[
    ],
    nested_types=[],
    enum_types=[
    ],
    options=None,
    is_extendable=False,
    syntax='proto3',
    extension_ranges=[],
    oneofs=[
    ],
    serialized_start=86,
    serialized_end=92,
)

DESCRIPTOR.message_types_by_name['Message'] = _MESSAGE
DESCRIPTOR.message_types_by_name['Resp'] = _RESP
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

Message = _reflection.GeneratedProtocolMessageType('Message', (_message.Message,), dict(
    DESCRIPTOR=_MESSAGE,
    __module__='examples.chat.chat_pb2'
    # @@protoc_insertion_point(class_scope:chat.Message)
))
_sym_db.RegisterMessage(Message)

Resp = _reflection.GeneratedProtocolMessageType('Resp', (_message.Message,), dict(
    DESCRIPTOR=_RESP,
    __module__='examples.chat.chat_pb2'
    # @@protoc_insertion_point(class_scope:chat.Resp)
))
_sym_db.RegisterMessage(Resp)


DESCRIPTOR.has_options = True
DESCRIPTOR._options = _descriptor._ParseOptions(
    descriptor_pb2.FileOptions(), _b('\220\001\001'))

_CHATSERVICE = _descriptor.ServiceDescriptor(
    name='ChatService',
    full_name='chat.ChatService',
    file=DESCRIPTOR,
    index=0,
    options=None,
    serialized_start=95,
    serialized_end=226,
    methods=[
        _descriptor.MethodDescriptor(
            name='Join',
            full_name='chat.ChatService.Join',
            index=0,
            containing_service=None,
            input_type=pymaid_dot_pb_dot_pymaid__pb2._VOID,
            output_type=_RESP,
            options=None,
        ),
        _descriptor.MethodDescriptor(
            name='Publish',
            full_name='chat.ChatService.Publish',
            index=1,
            containing_service=None,
            input_type=_MESSAGE,
            output_type=pymaid_dot_pb_dot_pymaid__pb2._VOID,
            options=None,
        ),
        _descriptor.MethodDescriptor(
            name='Leave',
            full_name='chat.ChatService.Leave',
            index=2,
            containing_service=None,
            input_type=pymaid_dot_pb_dot_pymaid__pb2._VOID,
            output_type=_RESP,
            options=None,
        ),
    ])
_sym_db.RegisterServiceDescriptor(_CHATSERVICE)

DESCRIPTOR.services_by_name['ChatService'] = _CHATSERVICE


_CHATBROADCAST = _descriptor.ServiceDescriptor(
    name='ChatBroadcast',
    full_name='chat.ChatBroadcast',
    file=DESCRIPTOR,
    index=1,
    options=None,
    serialized_start=228,
    serialized_end=286,
    methods=[
        _descriptor.MethodDescriptor(
            name='Publish',
            full_name='chat.ChatBroadcast.Publish',
            index=0,
            containing_service=None,
            input_type=_MESSAGE,
            output_type=pymaid_dot_pb_dot_pymaid__pb2._VOID,
            options=None,
        ),
    ])
_sym_db.RegisterServiceDescriptor(_CHATBROADCAST)

DESCRIPTOR.services_by_name['ChatBroadcast'] = _CHATBROADCAST

ChatService = service_reflection.GeneratedServiceType('ChatService', (_service.Service,), dict(
    DESCRIPTOR=_CHATSERVICE,
    __module__='examples.chat.chat_pb2'
))

ChatService_Stub = service_reflection.GeneratedServiceStubType('ChatService_Stub', (ChatService,), dict(
    DESCRIPTOR=_CHATSERVICE,
    __module__='examples.chat.chat_pb2'
))


ChatBroadcast = service_reflection.GeneratedServiceType('ChatBroadcast', (_service.Service,), dict(
    DESCRIPTOR=_CHATBROADCAST,
    __module__='examples.chat.chat_pb2'
))

ChatBroadcast_Stub = service_reflection.GeneratedServiceStubType('ChatBroadcast_Stub', (ChatBroadcast,), dict(
    DESCRIPTOR=_CHATBROADCAST,
    __module__='examples.chat.chat_pb2'
))


# @@protoc_insertion_point(module_scope)