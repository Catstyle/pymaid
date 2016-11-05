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

__version__ = re.search(
    "__version__\s*=\s*'(.*)'", open('pymaid/__init__.py').read(), re.M
).group(1)
assert __version__


def get_packages():
    # setuptools can't do the job :(
    packages = []
    for root, dirnames, filenames in os.walk('pymaid'):
        if '__init__.py' in filenames:
            packages.append(".".join(os.path.split(root)).strip("."))
    return packages


class clean(_clean):

    def run(self):
        # Delete generated files in the code tree.
        for (dirpath, dirnames, filenames) in os.walk("."):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if (filepath.endswith("_pb2.py") or
                        filepath.endswith(".pyc") or
                        filepath.endswith(".pb.js") or
                        filepath.endswith(".so") or
                        filepath.endswith(".o")):
                    os.remove(filepath)
            for dirname in dirnames:
                if dirname in ('build', 'dist', 'pymaid.egg-info', 'protos'):
                    shutil.rmtree(os.path.join(dirpath, dirname))
        # _clean is an old-style class, so super() doesn't work.
        _clean.run(self)


class build_py(_build_py):

    def run(self):
        errno = subprocess.call(
            ['python', 'compile.py', '.', '--python-out', '.'])
        if errno != 0:
            print('call `python compile.py` failed with errno: %d' % errno)
            exit(1)
        open('pymaid/pb/__init__.py', 'a').close()
        # _build_py is an old-style class, so super() doesn't work.
        _build_py.run(self)


if __name__ == '__main__':
    setup(
        name="pymaid",
        version=__version__,
        author="Catstyle",
        author_email="Catstyle.Lee@gmail.com",
        license="MIT",
        packages=get_packages(),
        zip_safe=False,
        data_files=[
            (os.path.join(sys.prefix, 'include', 'pymaid', 'pb'),
             ['pymaid/pb/pymaid.proto']),
        ],
        install_requires=[
            'gevent>=1.0.2',
            'protobuf>=3.0.0a3.dev0',
        ],
        cmdclass={'clean': clean, 'build_py': build_py},
    )
