# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: examples/pb/echo.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import service as _service
from google.protobuf import service_reflection
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


DESCRIPTOR = _descriptor.FileDescriptor(
    name='examples/pb/echo.proto',
    package='echo',
    syntax='proto3',
    serialized_options=b'\220\001\001',
    create_key=_descriptor._internal_create_key,
    serialized_pb=b'\n\x16\x65xamples/pb/echo.proto\x12\x04\x65\x63ho\"\x1a\n\x07Message\x12\x0f\n\x07message\x18\x01 \x01(\t2\xe1\x01\n\x0b\x45\x63hoService\x12\x30\n\x0eUnaryUnaryEcho\x12\r.echo.Message\x1a\r.echo.Message\"\x00\x12\x33\n\x0fUnaryStreamEcho\x12\r.echo.Message\x1a\r.echo.Message\"\x00\x30\x01\x12\x33\n\x0fStreamUnaryEcho\x12\r.echo.Message\x1a\r.echo.Message\"\x00(\x01\x12\x36\n\x10StreamStreamEcho\x12\r.echo.Message\x1a\r.echo.Message\"\x00(\x01\x30\x01\x42\x03\x90\x01\x01\x62\x06proto3'
)


_MESSAGE = _descriptor.Descriptor(
    name='Message',
    full_name='echo.Message',
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    create_key=_descriptor._internal_create_key,
    fields=[
        _descriptor.FieldDescriptor(
            name='message', full_name='echo.Message.message', index=0,
            number=1, type=9, cpp_type=9, label=1,
            has_default_value=False, default_value=b"".decode('utf-8'),
            message_type=None, enum_type=None, containing_type=None,
            is_extension=False, extension_scope=None,
            serialized_options=None, file=DESCRIPTOR, create_key=_descriptor._internal_create_key),
    ],
    extensions=[
    ],
    nested_types=[],
    enum_types=[
    ],
    serialized_options=None,
    is_extendable=False,
    syntax='proto3',
    extension_ranges=[],
    oneofs=[
    ],
    serialized_start=32,
    serialized_end=58,
)

DESCRIPTOR.message_types_by_name['Message'] = _MESSAGE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

Message = _reflection.GeneratedProtocolMessageType('Message', (_message.Message,), {
    'DESCRIPTOR': _MESSAGE,
    '__module__': 'examples.pb.echo_pb2'
    # @@protoc_insertion_point(class_scope:echo.Message)
})
_sym_db.RegisterMessage(Message)


DESCRIPTOR._options = None

_ECHOSERVICE = _descriptor.ServiceDescriptor(
    name='EchoService',
    full_name='echo.EchoService',
    file=DESCRIPTOR,
    index=0,
    serialized_options=None,
    create_key=_descriptor._internal_create_key,
    serialized_start=61,
    serialized_end=286,
    methods=[
        _descriptor.MethodDescriptor(
            name='UnaryUnaryEcho',
            full_name='echo.EchoService.UnaryUnaryEcho',
            index=0,
            containing_service=None,
            input_type=_MESSAGE,
            output_type=_MESSAGE,
            serialized_options=None,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.MethodDescriptor(
            name='UnaryStreamEcho',
            full_name='echo.EchoService.UnaryStreamEcho',
            index=1,
            containing_service=None,
            input_type=_MESSAGE,
            output_type=_MESSAGE,
            serialized_options=None,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.MethodDescriptor(
            name='StreamUnaryEcho',
            full_name='echo.EchoService.StreamUnaryEcho',
            index=2,
            containing_service=None,
            input_type=_MESSAGE,
            output_type=_MESSAGE,
            serialized_options=None,
            create_key=_descriptor._internal_create_key,
        ),
        _descriptor.MethodDescriptor(
            name='StreamStreamEcho',
            full_name='echo.EchoService.StreamStreamEcho',
            index=3,
            containing_service=None,
            input_type=_MESSAGE,
            output_type=_MESSAGE,
            serialized_options=None,
            create_key=_descriptor._internal_create_key,
        ),
    ])
_sym_db.RegisterServiceDescriptor(_ECHOSERVICE)

DESCRIPTOR.services_by_name['EchoService'] = _ECHOSERVICE

EchoService = service_reflection.GeneratedServiceType('EchoService', (_service.Service,), dict(
    DESCRIPTOR=_ECHOSERVICE,
    __module__='examples.pb.echo_pb2'
))

EchoService_Stub = service_reflection.GeneratedServiceStubType('EchoService_Stub', (EchoService,), dict(
    DESCRIPTOR=_ECHOSERVICE,
    __module__='examples.pb.echo_pb2'
))


# @@protoc_insertion_point(module_scope)