from __future__ import print_function

import os.path
import subprocess
import argparse

from distutils.spawn import find_executable
from string import Template

import pymaid
extra_include = '/'.join(pymaid.__path__[0].split('/')[:-1])

JS_TEMPLATE = Template("""(function(global) {
    var next = global['${package}'] = global['${package}'] || {};
    ${nexts}
})(this);
""")


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('path', type=str, help='protos path')
    parser.add_argument(
        '--protoc', default=find_executable('protoc'), help='protoc compiler'
    )
    parser.add_argument('--python-out', type=str, help='python output path')
    parser.add_argument(
        '--py-init', action='store_true', help='create python module init file'
    )
    parser.add_argument(
        '--js-out', type=str, help='create js runtime structrues using protoc'
    )
    parser.add_argument(
        '--js-package', type=str, default='pbs',
        help='js descriptor package name'
    )

    args = parser.parse_args()
    print(args)
    print()
    if not args.protoc:
        print('invalid protoc compiler')
        exit(1)

    return args


def get_protos(path):
    protos = []
    for root, dirnames, filenames in os.walk(path):
        for filename in filenames:
            if filename.endswith('.proto'):
                protos.append(os.path.join(root, filename))
    return protos


def pb2py(protoc, source, path, python_out):
    command = [
        protoc, '-I', '.', '-I', path, '-I', extra_include,
        '--python_out', python_out, source
    ]
    print('%s' % ' '.join(command))
    if subprocess.call(command) != 0:
        exit(1)


def pb2js(protoc, source, path, output_path):
    command = [
        protoc, '-I', '.', '-I', path, '-I', extra_include,
        '--js_out=one_output_file_per_input_file,binary:%s' % output_path,
        source
    ]
    print('%s' % ' '.join(command))
    if subprocess.call(command) != 0:
        exit(1)


def ensure_folder(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def save_to_file(output, content):
    ensure_folder(os.path.dirname(output))
    with open(output, 'w') as fp:
        fp.write(content)


def generate(path, protoc=None, python_out='', py_init=False,
             js_out='', js_package='pbs'):
    if python_out:
        assert protoc, 'generate python require `protoc`'
        ensure_folder(python_out)
    if js_out:
        assert protoc, 'generate js/json require `protoc`'
        ensure_folder(js_out)

    protos = get_protos(path)
    for source in protos:
        if not os.path.exists(source):
            print('cannot find required file: %s\n' % source)
            exit(1)
        print('compiling %s' % source)
        if python_out:
            pb2py(protoc, source, path, python_out)
        if js_out:
            pb2js(protoc, source, path, js_out)
        print()

    if python_out and py_init:
        for root, dirs, files in os.walk(python_out):
            init_file = os.path.join(root, '__init__.py')
            if not os.path.exists(init_file):
                with open(init_file, 'a'):
                    pass


def main():
    args = parse_args()
    generate(**dict(args._get_kwargs()))


if __name__ == '__main__':
    main()
