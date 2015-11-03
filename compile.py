from __future__ import print_function

import sys
import os.path
import subprocess
import argparse
import json

from distutils.spawn import find_executable

prefix = sys.prefix
extra_include = os.path.join(prefix, 'include/')


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--protoc', default=find_executable('protoc'), help='protoc compiler'
    )
    parser.add_argument(
        '--pblua', default=find_executable('protoc-gen-lua'),
        help='protoc compiler lua plugin'
    )
    parser.add_argument(
        '--pbjs', default=find_executable('pbjs'), help='protoc compiler'
    )
    parser.add_argument(
        '--path', type=str, default='.', help='protos path'
    )
    parser.add_argument(
        '--python-out', type=str, default='.', help='python output path'
    )
    parser.add_argument(
        '--lua-out', type=str, default='',
        help='create lua runtime structrues using protoc-gen-lua plugin'
    )
    parser.add_argument(
        '--js-out', type=str, default='',
        help='create js runtime structrues using pbjs'
    )
    parser.add_argument(
        '--json-out', type=str, default='',
        help='create json descriptor using pbjs'
    )
    parser.add_argument(
        '--xor-key', type=str, default='',
        help='encode json descriptor by key'
    )

    args = parser.parse_args()
    print (args)
    print ()
    if not args.protoc:
        print ('invalid protoc compiler')
        exit(1)

    return args


def get_protos(path):
    protos = []
    for root, dirnames, filenames in os.walk(path):
        for filename in filenames:
            if filename.endswith('.proto'):
                protos.append(os.path.join(root, filename))
    return protos 


def compile_proto(protoc, source, path, python_out, lua_out=None):
    ensure_folder(python_out)
    command = [
        protoc, '-I', path, '-I', extra_include,
        '--python_out', python_out, source
    ]
    if lua_out:
        command.insert(-1, '--lua_out')
        command.insert(-1, lua_out)
    print ('protoc %s' % command)
    if subprocess.call(command) != 0:
        exit(1)


def _pbjs(pbjs, source, path, extra_command):
    command = [pbjs, source, '-p', path, '-p', extra_include]
    command.extend(extra_command)
    print ('pbjs %s' % command)
    return subprocess.check_output(command)


def pb2js(pbjs, source, path, output_path):
    content = _pbjs(pbjs, source, path, ['-t', 'js'])
    output = source.replace('.proto', '.js')
    save_to_file(os.path.join(output_path, output), content)


def pb2json(pbjs, source, path, output_path, xor_key):
    content = _pbjs(pbjs, source, path, ['-t', 'json'])
    content = json.dumps(json.loads(content))
    if xor_key:
        content = xor(content, xor_key)
    output = source.replace('.proto', '.json')
    save_to_file(os.path.join(output_path, output), content)


def xor(content, key):
    key = key.strip()
    assert key, 'invalid key'
    length = len(key)
    print ('xor with key: %s, length: %d' % (key, length))
    return ''.join([chr(ord(char) ^ ord(key[idx%length]))
                    for idx, char in enumerate(content)])


def ensure_folder(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def save_to_file(output, content):
    ensure_folder(os.path.dirname(output))
    with open(output, 'w') as fp:
        fp.write(content)


def generate(protoc, path, python_out='.',
             pbjs=None, js_out='', json_out='', xor_key='',
             pblua=None, lua_out=''):
    if js_out or json_out:
        assert pbjs, 'generate js/json require `pbjs`'
    if lua_out:
        assert pblua, 'generate lua require `protoc-gen-lua`'

    protos = get_protos(path)
    for source in protos:
        if not os.path.exists(source):
            print ('cannot find required file: %s\n' % source)
            exit(1)
        print ('compiling %s' % source)
        compile_proto(protoc, source, path, python_out, lua_out)
        if js_out:
            pb2js(pbjs, source, path, js_out)
        if json_out:
            pb2json(pbjs, source, path, json_out, xor_key)
        print ()


def main():
    args = parse_args()
    generate(**dict(args._get_kwargs()))


if __name__ == '__main__':
    main()
