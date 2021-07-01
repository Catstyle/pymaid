# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: pymaid/ext/monitor/monitor.proto
"""Generated protocol buffer code."""
from pymaid.rpc.pb import pymaid_pb2 as pymaid_dot_rpc_dot_pb_dot_pymaid__pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import service as _service
from google.protobuf import service_reflection
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


DESCRIPTOR = _descriptor.FileDescriptor(
    name='pymaid/ext/monitor/monitor.proto',
    package='pymaid.ext.monitor',
    syntax='proto3',
    serialized_options=b'\220\001\001',
    create_key=_descriptor._internal_create_key,
    serialized_pb=b'\n pymaid/ext/monitor/monitor.proto\x12\x12pymaid.ext.monitor\x1a\x1apymaid/rpc/pb/pymaid.proto\"\x06\n\x04Pong2G\n\x0eMonitorService\x12\x35\n\x04Ping\x12\x13.pymaid.rpc.pb.Void\x1a\x18.pymaid.ext.monitor.PongB\x03\x90\x01\x01\x62\x06proto3',
    dependencies=[pymaid_dot_rpc_dot_pb_dot_pymaid__pb2.DESCRIPTOR, ])


_PONG = _descriptor.Descriptor(
    name='Pong',
    full_name='pymaid.ext.monitor.Pong',
    filename=None,
    file=DESCRIPTOR,
    containing_type=None,
    create_key=_descriptor._internal_create_key,
    fields=[
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
    serialized_start=84,
    serialized_end=90,
)

DESCRIPTOR.message_types_by_name['Pong'] = _PONG
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

Pong = _reflection.GeneratedProtocolMessageType('Pong', (_message.Message,), {
    'DESCRIPTOR': _PONG,
    '__module__': 'pymaid.ext.monitor.monitor_pb2'
    # @@protoc_insertion_point(class_scope:pymaid.ext.monitor.Pong)
})
_sym_db.RegisterMessage(Pong)


DESCRIPTOR._options = None

_MONITORSERVICE = _descriptor.ServiceDescriptor(
    name='MonitorService',
    full_name='pymaid.ext.monitor.MonitorService',
    file=DESCRIPTOR,
    index=0,
    serialized_options=None,
    create_key=_descriptor._internal_create_key,
    serialized_start=92,
    serialized_end=163,
    methods=[
        _descriptor.MethodDescriptor(
            name='Ping',
            full_name='pymaid.ext.monitor.MonitorService.Ping',
            index=0,
            containing_service=None,
            input_type=pymaid_dot_rpc_dot_pb_dot_pymaid__pb2._VOID,
            output_type=_PONG,
            serialized_options=None,
            create_key=_descriptor._internal_create_key,
        ),
    ])
_sym_db.RegisterServiceDescriptor(_MONITORSERVICE)

DESCRIPTOR.services_by_name['MonitorService'] = _MONITORSERVICE

MonitorService = service_reflection.GeneratedServiceType('MonitorService', (_service.Service,), dict(
    DESCRIPTOR=_MONITORSERVICE,
    __module__='pymaid.ext.monitor.monitor_pb2'
))

MonitorService_Stub = service_reflection.GeneratedServiceStubType('MonitorService_Stub', (MonitorService,), dict(
    DESCRIPTOR=_MONITORSERVICE,
    __module__='pymaid.ext.monitor.monitor_pb2'
))


# @@protoc_insertion_point(module_scope)
