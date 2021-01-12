.PHONY: _default clean compile test pytest release

PYTHON ?= python

_default: compile

clean:
	rm -fr dist/ build/ *.egg-info
	find . -name '__pycache__' | xargs rm -rf
	$(PYTHON) setup.py clean

compile: clean
	$(PYTHON) compile.py --python-out . .

test:
	PYTHONASYNCIODEBUG=1 $(PYTHON) setup.py test
	$(PYTHON) setup.py test

pytest:
	$(PYTHON) -m pip install -r requirements-dev.txt
	PYTHONASYNCIODEBUG=1 $(PYTHON) -m pytest --cov=pymaid -v
	$(PYTHON) -m pytest --cov=pymaid -v

release: clean compile test pytest
	$(PYTHON) setup.py sdist bdist_wheel
