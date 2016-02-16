from __future__ import print_function

import sys
import os.path
import argparse
import importlib

from string import Template
from google.protobuf import descriptor


TYPES, LABELS = {}, {}
for name, attr in descriptor.FieldDescriptor.__dict__.items():
    if name.startswith('TYPE_'):
        TYPES[attr] = name.lower().split('_')[-1]
    if name.startswith('LABEL_'):
        LABELS[attr] = name.lower().split('_')[-1]

SERVICE_TEMPLATE = Template("""(function(global) {
    (global['${package}'] = global['${package}'] || {})['${service_name}'] = {
        name: '${full_name}',
        messages: [],
${methods}
    };
})(this);
""")

METHOD_TEMPLATE = Template("""/**${req}${resp}
**/
${method_name}: function(controller, req, cb) {
    this.messages.push(['${method_name}', req]);${cb}
},
""")

indent = '\n        '
star_indent = '\n * '


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('module', type=str, help='module file')
    parser.add_argument('service', type=str, help='service name')
    parser.add_argument('-p', nargs='*', type=str, help='extra python path')
    parser.add_argument('--output', default='.', type=str, help='output path')
    parser.add_argument(
        '--package', type=str, default='pbimpl', help='js package name'
    )

    args = parser.parse_args()
    print (args)
    print ()

    return args


def parse_module(module_file, service_name):
    dirname = os.path.dirname(module_file)
    sys.path.append(dirname)

    module_name = module_file.replace('/', '.')
    if module_name.endswith('.py'):
        module_name = module_name[:-3]
    module = importlib.import_module(module_name)

    for attr in module.__dict__.values():
        if (isinstance(attr, descriptor.ServiceDescriptor) and
                attr.name == service_name):
            return attr


def extra_message(message, indent='    '):
    fields = []
    for field in message.fields:
        text = '%s%s: %s ' % (indent, field.name, LABELS[field.label])
        if field.type == descriptor.FieldDescriptor.TYPE_MESSAGE:
            fields.append(text + field.message_type.name)
            fields.extend(extra_message(field.message_type, indent+'    '))
        else:
            fields.append(text + TYPES[field.type])
    #print (fields)
    return fields


def generate_jsimpl(service_descriptor, package):
    methods = ['']
    service_name = service_descriptor.name
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


if __name__ == '__main__':
    args = parse_args()
    if args.p:
        sys.path.extend(args.p)
    service_descriptor = parse_module(args.module, args.service)
    assert service_descriptor
    impl = generate_jsimpl(service_descriptor, args.package)

    output = args.output
    if not os.path.exists(output):
        os.makedirs(output)
    with open(os.path.join(output, args.service.lower()) + '.js', 'w') as fp:
        fp.write(impl)
