#!/bin/bash
python ../../compile.py --python-out . --js-out . examples
python jsrpc.py .
python jsimpl.py .
