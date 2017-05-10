from __future__ import print_function

import re
import sys
import shutil
import subprocess

from os import path, walk, remove
from codecs import open

from setuptools import setup, find_packages
from setuptools.command.build_py import build_py
from distutils.command.clean import clean

pwd = path.abspath(path.dirname(__file__))
__version__ = re.search(
    "__version__\s*=\s*'(.*)'", open('pymaid/__init__.py').read(), re.M
).group(1)
assert __version__

# Get the long description from the README file
if path.exists(path.join(pwd, 'README.md')):
    with open(path.join(pwd, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()
else:
    long_description = 'not exists'


class MyClean(clean):

    def run(self):
        # Delete generated files in the code tree.
        for (dirpath, dirnames, filenames) in walk("."):
            for filename in filenames:
                filepath = path.join(dirpath, filename)
                if (filepath.endswith("_pb2.py") or
                        filepath.endswith(".pyc") or
                        filepath.endswith(".pb.js") or
                        filepath.endswith(".so") or
                        filepath.endswith(".o")):
                    remove(filepath)
            for dirname in dirnames:
                if dirname in ('build', 'dist', 'pymaid.egg-info', 'protos'):
                    shutil.rmtree(path.join(dirpath, dirname))
        clean.run(self)


class MyBuildPy(build_py):

    def run(self):
        errno = subprocess.call([
            'python', 'compile.py', '.', '--python-out', '.'
        ])
        if errno != 0 and errno != 2:
            print('call `python compile.py` failed with errno: %d' % errno)
            exit(errno)
        build_py.run(self)


if __name__ == '__main__':
    setup(
        name="pymaid",
        description='A rpc framework based on gevent/protobuf',
        long_description=long_description,
        author="Catstyle",
        author_email="Catstyle.Lee@gmail.com",
        url="https://github.com/catstyle/pymaid",
        version=__version__,
        license="MIT",

        keywords='rpc gevent protobuf',
        classifiers=[
            # How mature is this project? Common values are
            #   3 - Alpha
            #   4 - Beta
            #   5 - Production/Stable
            'Development Status :: 3 - Alpha',

            # Indicate who your project is intended for
            'Intended Audience :: Developers',
            'Topic :: Software Development :: Build Tools',

            # Pick your license as you wish (should match "license" above)
            'License :: OSI Approved :: MIT License',

            # Specify the Python versions you support here.
            # In particular, ensure that you indicate whether you support
            # Python 2, Python 3 or both.
            'Programming Language :: Python :: 2.7',
        ],

        packages=find_packages(),
        data_files=[
            (path.join(sys.prefix, 'include', 'pymaid', 'pb'),
             ['pymaid/pb/pymaid.proto']),
        ],
        install_requires=[
            'gevent>=1.2',
            'protobuf>=3.2.0',
            'six',
            'ujson',
            'wsaccel',
        ],
        tests_require=[
            'websocket-client',
        ],
        cmdclass={'build_py': MyBuildPy, 'clean': MyClean},
    )
