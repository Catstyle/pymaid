# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: examples/reraise/rpc.proto

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
    name='examples/reraise/rpc.proto',
    package='reraise',
    syntax='proto3',
    serialized_pb=_b('\n\x1a\x65xamples/reraise/rpc.proto\x12\x07reraise\"\x19\n\x06UserId\x12\x0f\n\x07user_id\x18\x01 \x01(\r\"+\n\x06Player\x12\x0f\n\x07user_id\x18\x01 \x01(\r\x12\x10\n\x08nickname\x18\x02 \x01(\t2A\n\x0bRemoteError\x12\x32\n\x0eplayer_profile\x12\x0f.reraise.UserId\x1a\x0f.reraise.PlayerB\x03\x90\x01\x01\x62\x06proto3')
)


_USERID = _descriptor.Descriptor(
    name='UserId',
    full_name='reraise.UserId',
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    fields=[
        _descriptor.FieldDescriptor(
            name='user_id', full_name='reraise.UserId.user_id', index=0,
            number=1, type=13, cpp_type=3, label=1,
            has_default_value=False, default_value=0,
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
    serialized_start=39,
    serialized_end=64,
)


_PLAYER = _descriptor.Descriptor(
    name='Player',
    full_name='reraise.Player',
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    fields=[
        _descriptor.FieldDescriptor(
            name='user_id', full_name='reraise.Player.user_id', index=0,
            number=1, type=13, cpp_type=3, label=1,
            has_default_value=False, default_value=0,
            message_type=None, enum_type=None, containing_type=None,
            is_extension=False, extension_scope=None,
            options=None, file=DESCRIPTOR),
        _descriptor.FieldDescriptor(
            name='nickname', full_name='reraise.Player.nickname', index=1,
            number=2, type=9, cpp_type=9, label=1,
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
    serialized_start=66,
    serialized_end=109,
)

DESCRIPTOR.message_types_by_name['UserId'] = _USERID
DESCRIPTOR.message_types_by_name['Player'] = _PLAYER
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

UserId = _reflection.GeneratedProtocolMessageType('UserId', (_message.Message,), dict(
    DESCRIPTOR=_USERID,
    __module__='examples.reraise.rpc_pb2'
    # @@protoc_insertion_point(class_scope:reraise.UserId)
))
_sym_db.RegisterMessage(UserId)

Player = _reflection.GeneratedProtocolMessageType('Player', (_message.Message,), dict(
    DESCRIPTOR=_PLAYER,
    __module__='examples.reraise.rpc_pb2'
    # @@protoc_insertion_point(class_scope:reraise.Player)
))
_sym_db.RegisterMessage(Player)


DESCRIPTOR.has_options = True
DESCRIPTOR._options = _descriptor._ParseOptions(
    descriptor_pb2.FileOptions(), _b('\220\001\001'))

_REMOTEERROR = _descriptor.ServiceDescriptor(
    name='RemoteError',
    full_name='reraise.RemoteError',
    file=DESCRIPTOR,
    index=0,
    options=None,
    serialized_start=111,
    serialized_end=176,
    methods=[
        _descriptor.MethodDescriptor(
            name='player_profile',
            full_name='reraise.RemoteError.player_profile',
            index=0,
            containing_service=None,
            input_type=_USERID,
            output_type=_PLAYER,
            options=None,
        ),
    ])
_sym_db.RegisterServiceDescriptor(_REMOTEERROR)

DESCRIPTOR.services_by_name['RemoteError'] = _REMOTEERROR

RemoteError = service_reflection.GeneratedServiceType('RemoteError', (_service.Service,), dict(
    DESCRIPTOR=_REMOTEERROR,
    __module__='examples.reraise.rpc_pb2'
))

RemoteError_Stub = service_reflection.GeneratedServiceStubType('RemoteError_Stub', (RemoteError,), dict(
    DESCRIPTOR=_REMOTEERROR,
    __module__='examples.reraise.rpc_pb2'
))


# @@protoc_insertion_point(module_scope)
