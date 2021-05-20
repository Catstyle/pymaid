# /bin/sh
make clean
make compile
make test
make release_sdist

PYTHON=python3.7 make release_wheel
PYTHON=python3.8 make release_wheel
PYTHON=python3.9 make release_wheel

make upload
