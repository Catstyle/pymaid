from __future__ import print_function

import re
import subprocess

from pathlib import Path

from setuptools import setup, find_packages, Extension
from setuptools.command.build_py import build_py

root_dir = Path(__file__).parent
__version__ = re.search(
    "__version__ = '(.*)'",
    (root_dir / 'pymaid/__init__.py').read_text(encoding='utf-8'),
    re.M
).group(1)
assert __version__

# Get the long description from the README file
long_description = (root_dir / 'README.md').read_text(encoding='utf-8')

requirements = (root_dir / 'requirements.txt').read_text(encoding='utf-8')
requirements = [line.strip() for line in requirements.split('\n')]

dev_requirements = (root_dir / 'requirements-dev.txt')
dev_requirements = [
    line.strip()
    for line in dev_requirements.read_text(encoding='utf-8').split('\n')
]


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

        keywords='asyncio network rpc framework',
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
            'Programming Language :: Python :: 3.8',
        ],
        python_requires='>=3.8',

        packages=find_packages(),
        package_data={
            '': ['*.proto'],
        },
        install_requires=requirements,
        tests_require=dev_requirements,
        extras_require={
            'backend': [
                'requests==2.21.0', 'PyYAML==3.13', 'xmltodict==0.12.0'
            ],
        },
        ext_modules=[
            Extension(
                'pymaid.net.ws.speedups',
                sources=['pymaid/net/ws/speedups.c'],
                optional=not (root_dir / '.cibuildwheel').exists(),
            )
        ],

        cmdclass={'build_py': MyBuildPy},
    )
