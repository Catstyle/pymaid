# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: examples/reraise_error/pb/rpc.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
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
  name='examples/reraise_error/pb/rpc.proto',
  package='reraise',
  serialized_pb=_b('\n#examples/reraise_error/pb/rpc.proto\x12\x07reraise\"\x06\n\x04Void2?\n\x0bRemoteError\x12\x30\n\x10player_not_exist\x12\r.reraise.Void\x1a\r.reraise.VoidB\x03\x90\x01\x01\x62\x06proto3')
)
_sym_db.RegisterFileDescriptor(DESCRIPTOR)




_VOID = _descriptor.Descriptor(
  name='Void',
  full_name='reraise.Void',
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
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=48,
  serialized_end=54,
)

DESCRIPTOR.message_types_by_name['Void'] = _VOID

Void = _reflection.GeneratedProtocolMessageType('Void', (_message.Message,), dict(
  DESCRIPTOR = _VOID,
  __module__ = 'examples.reraise_error.pb.rpc_pb2'
  # @@protoc_insertion_point(class_scope:reraise.Void)
  ))
_sym_db.RegisterMessage(Void)


DESCRIPTOR.has_options = True
DESCRIPTOR._options = _descriptor._ParseOptions(descriptor_pb2.FileOptions(), _b('\220\001\001'))

_REMOTEERROR = _descriptor.ServiceDescriptor(
  name='RemoteError',
  full_name='reraise.RemoteError',
  file=DESCRIPTOR,
  index=0,
  options=None,
  serialized_start=56,
  serialized_end=119,
  methods=[
  _descriptor.MethodDescriptor(
    name='player_not_exist',
    full_name='reraise.RemoteError.player_not_exist',
    index=0,
    containing_service=None,
    input_type=_VOID,
    output_type=_VOID,
    options=None,
  ),
])

RemoteError = service_reflection.GeneratedServiceType('RemoteError', (_service.Service,), dict(
  DESCRIPTOR = _REMOTEERROR,
  __module__ = 'examples.reraise_error.pb.rpc_pb2'
  ))

RemoteError_Stub = service_reflection.GeneratedServiceStubType('RemoteError_Stub', (RemoteError,), dict(
  DESCRIPTOR = _REMOTEERROR,
  __module__ = 'examples.reraise_error.pb.rpc_pb2'
  ))


# @@protoc_insertion_point(module_scope)
