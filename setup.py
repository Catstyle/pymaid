from __future__ import print_function

import re
import os
import sys
import shutil
import subprocess

from setuptools import setup
from distutils.command.clean import clean as _clean
if sys.version_info[0] >= 3:
    # Python 3
    from distutils.command.build_py import build_py_2to3 as _build_py
else:
    # Python 2
    from distutils.command.build_py import build_py as _build_py
from distutils.spawn import find_executable

__version__ = re.search(
    "__version__\s*=\s*'(.*)'", open('pymaid/__init__.py').read(), re.M
).group(1)
assert __version__


protoc = find_executable("protoc")
protoc_lua = find_executable("protoc-gen-lua")
if not protoc:
    sys.stderr.write(
        "protoc is not installed, Please compile it "
        "or install the binary package.\n"
    )
    sys.exit(-1)


def get_packages():
    # setuptools can't do the job :(
    packages = []
    for root, dirnames, filenames in os.walk('pymaid'):
        if '__init__.py' in filenames:
            packages.append(".".join(os.path.split(root)).strip("."))
    return packages


def get_protos():
    # setuptools can't do the job :(
    protos = []
    for root, dirnames, filenames in os.walk('.'):
        for filename in filenames:
            if filename.endswith('.proto'):
                protos.append(os.path.join(root, filename))
    return protos 


def generate_proto(source):
    """Invokes the Protocol Compiler to generate a _pb2.py from the given
    .proto file.  Does nothing if the output already exists and is newer than
    the input."""

    output = source.replace(".proto", "_pb2.py")

    print("Generating %s..." % output)
    if not os.path.exists(source):
        sys.stderr.write("Can't find required file: %s\n" % source)
        sys.exit(-1)

    protoc_command = [protoc, "-I.", "--python_out=.", source]
    if gen_lua_pb and protoc_lua:
        protoc_command.insert(-1, "--lua_out=.")
    if subprocess.call(protoc_command) != 0:
        sys.exit(-1)


class clean(_clean):

    def run(self):
        # Delete generated files in the code tree.
        for (dirpath, dirnames, filenames) in os.walk("."):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if (filepath.endswith("_pb2.py") or
                        filepath.endswith(".pyc") or
                        filepath.endswith(".so") or
                        filepath.endswith(".o")):
                    os.remove(filepath)
            for dirname in dirnames:
                if dirname in ('build', 'dist', 'pymaid.egg-info'):
                    shutil.rmtree(os.path.join(dirpath, dirname))
        # _clean is an old-style class, so super() doesn't work.
        _clean.run(self)


class build_py(_build_py):

    def run(self):
        for proto in get_protos():
            generate_proto(proto)
        open('pymaid/pb/__init__.py', 'a').close()
        # _build_py is an old-style class, so super() doesn't work.
        _build_py.run(self)


gen_lua_pb = False
if __name__ == '__main__':
    if '--gen_lua_pb' in sys.argv:
        gen_lua_pb = True
        sys.argv.remove('--gen_lua_pb')
    setup(
        name="pymaid",
        version=__version__,
        author="Catstyle",
        author_email="Catstyle.Lee@gmail.com",
        license="do what the f**k you want",
        packages=get_packages(),
        zip_safe=True,
        data_files = [
            (os.path.join(sys.prefix, 'include', 'pymaid', 'pb'),
             ['pymaid/pb/pymaid.proto']),
        ],
        install_requires=[
            'gevent>=1.0.1',
            'protobuf>=3.0.0a3.dev0',
        ],
        cmdclass = {'clean': clean, 'build_py': build_py},
    )
