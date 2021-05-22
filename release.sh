# /bin/sh
make clean
make release_sdist

PYTHON=python3.7 make compile release_wheel
PYTHON=python3.8 make compile release_wheel
PYTHON=python3.9 make compile release_wheel
