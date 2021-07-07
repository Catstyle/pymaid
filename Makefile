.PHONY: _default clean compile test release docs

PYTHON ?= python

UNAME := $(shell uname)
UNAME_M := $(shell uname -m)
OPTS :=
ifeq ($(UNAME),Darwin)
	OPTS += --plat-name macosx_10_9_$(UNAME_M)
endif
ifeq ($(UNAME),Linux)
	OPTS += --plat-name manylinux1_$(UNAME_M)
endif

_default: compile

clean:
	rm -fr dist/ build/ *.egg-info .eggs .coverage* .pytest_cache
	find . -name '__pycache__' | xargs rm -rf
	$(PYTHON) setup.py clean

compile:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) compile.py --python-out . .
	-pre-commit run -a
	$(PYTHON) setup.py build

test:
	$(PYTHON) -m pip install -r requirements-dev.txt
	PYTHONASYNCIODEBUG=1 $(PYTHON) -m pytest --cov=pymaid -v
	$(PYTHON) -m pytest --cov=pymaid -v

release_sdist:
	$(PYTHON) setup.py sdist

release_wheel:
	$(PYTHON) -m pip install -U pip wheel
	$(PYTHON) setup.py bdist_wheel $(OPTS)

upload:
	twine upload dist/*

docs:
	sphinx-build -b html -n -d build/doctrees -j auto -W docs docs/html
