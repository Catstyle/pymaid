# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: pymaid/pb/pymaid.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='pymaid/pb/pymaid.proto',
  package='pymaid.pb',
  serialized_pb=_b('\n\x16pymaid/pb/pymaid.proto\x12\tpymaid.pb\"\xaa\x01\n\nController\x12\x14\n\x0cservice_name\x18\x01 \x01(\t\x12\x13\n\x0bmethod_name\x18\x02 \x01(\t\x12\x17\n\x0ftransmission_id\x18\x03 \x01(\r\x12\x13\n\x0bis_canceled\x18\x04 \x01(\x08\x12\x11\n\tis_failed\x18\x05 \x01(\x08\x12\x17\n\x0c\x63ontent_size\x18\x06 \x01(\r:\x01\x30\x12\x17\n\x0fis_notification\x18\x07 \x01(\x08\"\x06\n\x04Void\"9\n\x0c\x45rrorMessage\x12\x12\n\nerror_code\x18\x01 \x02(\r\x12\x15\n\rerror_message\x18\x02 \x02(\t')
)
_sym_db.RegisterFileDescriptor(DESCRIPTOR)




_CONTROLLER = _descriptor.Descriptor(
  name='Controller',
  full_name='pymaid.pb.Controller',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='service_name', full_name='pymaid.pb.Controller.service_name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='method_name', full_name='pymaid.pb.Controller.method_name', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='transmission_id', full_name='pymaid.pb.Controller.transmission_id', index=2,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='is_canceled', full_name='pymaid.pb.Controller.is_canceled', index=3,
      number=4, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='is_failed', full_name='pymaid.pb.Controller.is_failed', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='content_size', full_name='pymaid.pb.Controller.content_size', index=5,
      number=6, type=13, cpp_type=3, label=1,
      has_default_value=True, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='is_notification', full_name='pymaid.pb.Controller.is_notification', index=6,
      number=7, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
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
  serialized_start=38,
  serialized_end=208,
)


_VOID = _descriptor.Descriptor(
  name='Void',
  full_name='pymaid.pb.Void',
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
  serialized_start=210,
  serialized_end=216,
)


_ERRORMESSAGE = _descriptor.Descriptor(
  name='ErrorMessage',
  full_name='pymaid.pb.ErrorMessage',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='error_code', full_name='pymaid.pb.ErrorMessage.error_code', index=0,
      number=1, type=13, cpp_type=3, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='error_message', full_name='pymaid.pb.ErrorMessage.error_message', index=1,
      number=2, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
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
  serialized_start=218,
  serialized_end=275,
)

DESCRIPTOR.message_types_by_name['Controller'] = _CONTROLLER
DESCRIPTOR.message_types_by_name['Void'] = _VOID
DESCRIPTOR.message_types_by_name['ErrorMessage'] = _ERRORMESSAGE

Controller = _reflection.GeneratedProtocolMessageType('Controller', (_message.Message,), dict(
  DESCRIPTOR = _CONTROLLER,
  __module__ = 'pymaid.pb.pymaid_pb2'
  # @@protoc_insertion_point(class_scope:pymaid.pb.Controller)
  ))
_sym_db.RegisterMessage(Controller)

Void = _reflection.GeneratedProtocolMessageType('Void', (_message.Message,), dict(
  DESCRIPTOR = _VOID,
  __module__ = 'pymaid.pb.pymaid_pb2'
  # @@protoc_insertion_point(class_scope:pymaid.pb.Void)
  ))
_sym_db.RegisterMessage(Void)

ErrorMessage = _reflection.GeneratedProtocolMessageType('ErrorMessage', (_message.Message,), dict(
  DESCRIPTOR = _ERRORMESSAGE,
  __module__ = 'pymaid.pb.pymaid_pb2'
  # @@protoc_insertion_point(class_scope:pymaid.pb.ErrorMessage)
  ))
_sym_db.RegisterMessage(ErrorMessage)


# @@protoc_insertion_point(module_scope)
