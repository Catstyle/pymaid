# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: examples/echo/echo.proto

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


DESCRIPTOR = _descriptor.FileDescriptor(
    name='examples/echo/echo.proto',
    package='echo',
    syntax='proto3',
    serialized_pb=_b('\n\x18\x65xamples/echo/echo.proto\x12\x04\x65\x63ho\"\x1a\n\x07Message\x12\x0f\n\x07message\x18\x01 \x01(\t23\n\x0b\x45\x63hoService\x12$\n\x04\x65\x63ho\x12\r.echo.Message\x1a\r.echo.MessageB\x03\x90\x01\x01\x62\x06proto3')
)


_MESSAGE = _descriptor.Descriptor(
    name='Message',
    full_name='echo.Message',
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    fields=[
        _descriptor.FieldDescriptor(
            name='message', full_name='echo.Message.message', index=0,
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
    serialized_start=34,
    serialized_end=60,
)

DESCRIPTOR.message_types_by_name['Message'] = _MESSAGE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

Message = _reflection.GeneratedProtocolMessageType('Message', (_message.Message,), dict(
    DESCRIPTOR=_MESSAGE,
    __module__='examples.echo.echo_pb2'
    # @@protoc_insertion_point(class_scope:echo.Message)
))
_sym_db.RegisterMessage(Message)


DESCRIPTOR.has_options = True
DESCRIPTOR._options = _descriptor._ParseOptions(
    descriptor_pb2.FileOptions(), _b('\220\001\001'))

_ECHOSERVICE = _descriptor.ServiceDescriptor(
    name='EchoService',
    full_name='echo.EchoService',
    file=DESCRIPTOR,
    index=0,
    options=None,
    serialized_start=62,
    serialized_end=113,
    methods=[
        _descriptor.MethodDescriptor(
            name='echo',
            full_name='echo.EchoService.echo',
            index=0,
            containing_service=None,
            input_type=_MESSAGE,
            output_type=_MESSAGE,
            options=None,
        ),
    ])
_sym_db.RegisterServiceDescriptor(_ECHOSERVICE)

DESCRIPTOR.services_by_name['EchoService'] = _ECHOSERVICE

EchoService = service_reflection.GeneratedServiceType('EchoService', (_service.Service,), dict(
    DESCRIPTOR=_ECHOSERVICE,
    __module__='examples.echo.echo_pb2'
))

EchoService_Stub = service_reflection.GeneratedServiceStubType('EchoService_Stub', (EchoService,), dict(
    DESCRIPTOR=_ECHOSERVICE,
    __module__='examples.echo.echo_pb2'
))


# @@protoc_insertion_point(module_scope)