from __future__ import print_function

import sys
import os
import argparse
import imp

from string import Template
from google.protobuf.service_reflection import GeneratedServiceType


SERVICE_TEMPLATE = Template("""${requires}
(function(global) {
    (global['${package}'] = global['${package}'] || {})['${service_name}'] = {
        name: '${full_name}',
${methods}
    };
})(this);
""")

METHOD_TEMPLATE = Template("""
${method_name}: {
    input_type: ${input_type},
    output_type: ${output_type},
},
""")

REQUIRE_TEMPLATE = Template("""goog.require('${name}');""")

indent = '\n        '
star_indent = '\n * '


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('path', type=str, help='module file path')
    parser.add_argument(
        '--root', default='.', type=str, help='root python path'
    )
    parser.add_argument('--output', default='.', type=str, help='output path')
    parser.add_argument(
        '--package', type=str, default='pbrpc', help='js package name'
    )
    parser.add_argument(
        '--prefix', type=str, default='proto', help='js proto prefix name'
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
        if (isinstance(attr, GeneratedServiceType)
                and attr.DESCRIPTOR.name.endswith('Service')):
            yield attr


def generate_js_rpc(service_descriptor, package, prefix):
    methods = []
    requires = set()
    service_name = service_descriptor.name
    print('generating %s' % service_descriptor.full_name)
    for method in service_descriptor.methods:
        input_type = prefix + '.' + method.input_type.full_name
        output_type = prefix + '.' + method.output_type.full_name
        requires.update([REQUIRE_TEMPLATE.safe_substitute(name=input_type),
                         REQUIRE_TEMPLATE.safe_substitute(name=output_type)])
        mstr = METHOD_TEMPLATE.safe_substitute(
            method_name=method.name,
            input_type=input_type,
            output_type=output_type,
        )
        methods.append(indent.join(mstr.split('\n')))
    return SERVICE_TEMPLATE.safe_substitute(
        requires='\n'.join(sorted(requires)), package=package,
        full_name=service_descriptor.full_name,
        service_name=service_name, methods=indent.join(methods),
    )


def generate(path, output, package, prefix, root):
    sys.path.append(path)
    for module in get_modules(path):
        mod = import_module(module)
        for service in parse_module(mod):
            content = generate_js_rpc(service.DESCRIPTOR, package, prefix)

            splits = os.path.relpath(module, path).split('/')
            output_path = os.path.join(output, '/'.join(splits[:-1]))
            if not os.path.exists(output_path):
                os.makedirs(output_path)
            file_path = os.path.join(output_path, splits[-1][:-7])
            with open(file_path + '_rpc.js', 'w') as fp:
                fp.write(content)


if __name__ == '__main__':
    args = parse_args()
    generate(args.path, args.output, args.package, args.prefix, args.root)
