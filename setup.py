import os
import sys
from setuptools import setup, find_packages
from pymaid import __version__


setup(
    name="pymaid",
    version=__version__,
    author="Catstyle",
    author_email="Catstyle.Lee@gmail.com",
    license="do what the f**k you want",
    packages=find_packages(exclude='examples'),
    zip_safe=True,
    data_files = [
        (os.path.join(sys.prefix, 'include', 'pymaid', 'pb'),
         ['pymaid/pb/pymaid.proto']),
    ],
    install_requires=[
        'gevent>=1.0',
        'protobuf>=2.6',
    ],
)
