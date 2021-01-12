.PHONY: _default clean compile test release

PYTHON ?= python

_default: compile

clean:
	rm -fr dist/ build/ *.egg-info .eggs .coverage .pytest_cache
	find . -name '__pycache__' | xargs rm -rf
	$(PYTHON) setup.py clean

compile: clean
	$(PYTHON) compile.py --python-out . .
	$(PYTHON) setup.py build
	pre-commit run -a

test:
	$(PYTHON) -m pip install -r requirements-dev.txt
	PYTHONASYNCIODEBUG=1 $(PYTHON) -m pytest --cov=pymaid -v
	$(PYTHON) -m pytest --cov=pymaid -v

release: clean compile test
	$(PYTHON) setup.py sdist bdist_wheel
