from __future__ import print_function

import os.path
import argparse
import imp

from string import Template
from google.protobuf import descriptor
from google.protobuf.service_reflection import GeneratedServiceType


TYPES, LABELS = {}, {}
for name, attr in descriptor.FieldDescriptor.__dict__.items():
    if name.startswith('TYPE_'):
        TYPES[attr] = name.lower().split('_')[-1]
    if name.startswith('LABEL_'):
        LABELS[attr] = name.lower().split('_')[-1]

SERVICE_TEMPLATE = Template("""(function(global) {
    (global['${package}'] = global['${package}'] || {})['${service_name}'] = {
        name: '${full_name}',
        listeners: [],

        registerListener: function(listener) {
            this.listeners.push(listener);
        },

        unregisterListener: function(listener) {
            this.listeners.splice(this.listeners.indexOf(listener), 1);
        },
${methods}
    };
})(this);
""")

METHOD_TEMPLATE = Template("""/**${req}${resp}
**/
${method_name}: function(controller, req, cb) {
    this.listeners.forEach(function(listener) {
        listener.dispatch(['${method_name}', req]);
    });
},
""")

indent = '\n        '
star_indent = '\n * '


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('path', type=str, help='module file')
    parser.add_argument(
        '--root', default='.', type=str, help='extra python path'
    )
    parser.add_argument('--output', default='.', type=str, help='output path')
    parser.add_argument(
        '--package', type=str, default='pbimpl', help='js package name'
    )

    args = parser.parse_args()
    print(args)
    print()

    return args


def get_modules(root_path):
    modules = []
    for root, dirnames, filenames in os.walk(root_path):
        for filename in filenames:
            if filename.endswith('_pb2.py'):
                modules.append(os.path.join(root, filename))
    print('modules', modules)
    return modules


def import_module(module_file):
    module_name = module_file.split('/')[-1]
    if module_name.endswith('.py'):
        module_name = module_name[:-3]
    return imp.load_source(module_name, module_file)


def parse_module(module):
    for attr in module.__dict__.values():
        if (isinstance(attr, GeneratedServiceType) and
                attr.DESCRIPTOR.name.endswith('Broadcast')):
            yield attr


def extra_message(message, indent='    '):
    fields = []
    for field in message.fields:
        text = '%s%s: %s ' % (indent, field.name, LABELS[field.label])
        if field.type == descriptor.FieldDescriptor.TYPE_MESSAGE:
            fields.append(text + field.message_type.name)
            fields.extend(extra_message(field.message_type, indent + '    '))
        else:
            fields.append(text + TYPES[field.type])
    # print (fields)
    return fields


def generate_jsimpl(service_descriptor, package):
    methods = ['']
    service_name = service_descriptor.name
    print('generating %s' % service_descriptor.full_name)
    for method in service_descriptor.methods:
        req = star_indent + 'req: ' + method.input_type.name + star_indent
        req += star_indent.join(extra_message(method.input_type))
        resp = star_indent + 'resp: ' + method.output_type.name + star_indent
        resp += star_indent.join(extra_message(method.output_type))
        cb = '\n    cb(controller, req);'
        if method.output_type.name == 'Void':
            cb = ''
        mstr = METHOD_TEMPLATE.safe_substitute(
            req=req, resp=resp, service_name=service_name,
            method_name=method.name, cb=cb
        )
        methods.append(indent.join(mstr.split('\n')))
    return SERVICE_TEMPLATE.safe_substitute(
        package=package, full_name=service_descriptor.full_name,
        service_name=service_name, methods=indent.join(methods),
    )


def generate(path, output, package, root):
    for module in get_modules(path):
        mod = import_module(module)
        for service in parse_module(mod):
            content = generate_jsimpl(service.DESCRIPTOR, package)

            splits = os.path.relpath(module, path).split('/')
            output_path = os.path.join(output, '/'.join(splits[:-1]))
            if not os.path.exists(output_path):
                os.makedirs(output_path)
            file_path = os.path.join(output_path, splits[-1][:-7])
            with open(file_path + '_broadcast.js', 'w') as fp:
                fp.write(content)


if __name__ == '__main__':
    args = parse_args()
    generate(args.path, args.output, args.package, args.root)
