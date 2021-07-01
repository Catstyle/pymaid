#! /bin/bash
export PYTHONPATH=.:$PYTHONPATH

echo
name='net'
echo 'checking '${name}', clients: 100, request/client: 1000'
python -O examples/$name/server.py --uvloop > /dev/null 2>&1 &
sid=$!
sleep 0.2
time python -O examples/$name/client.py --uvloop -c 100 -r 1000 > /dev/null 2>&1
disown -r
kill $sid
echo 'done '${name}', clients: 100, request/client: 1000'

echo
name='pb'
echo 'checking '${name}', clients: 100, request/client: 100'
python -O examples/$name/server.py --uvloop > /dev/null 2>&1 &
sid=$!
sleep 0.2
time python -O examples/$name/client.py --uvloop -c 100 -r 100 > /dev/null 2>&1
echo 'done '${name}', clients: 100, request/client: 100'

echo
echo 'checking '${name}', clients: 100, request/client: 1000'
time python -O examples/$name/client.py --uvloop -c 100 -r 1000 > /dev/null 2>&1
disown -r
kill $sid
echo 'done '${name}', clients: 100, request/client: 1000'

echo
name='heartbeat'
echo 'checking '${name}', clients: 1000'
python -O examples/$name/server.py --uvloop 1 1 > /dev/null 2>&1 &
sid=$!
sleep 0.2
time python -O examples/$name/client.py --uvloop -c 1000 > /dev/null 2>&1
disown -r
kill $sid
echo 'done '${name}', clients: 1000'

echo
name='echo_ws'
echo 'checking '${name}', clients: 100, request/client: 1000'
python -O examples/$name/server.py --uvloop > /dev/null 2>&1 &
sid=$!
sleep 0.2
time python -O examples/$name/client.py --uvloop -c 100 -r 1000 > /dev/null 2>&1
echo 'done '${name}', clients: 100, request/client: 1000'

echo
echo 'checking '${name}', clients: 100, request/client: 10000'
time python -O examples/$name/client.py --uvloop -c 100 -r 10000 > /dev/null 2>&1
disown -r
kill $sid
echo 'done '${name}', clients: 100, request/client: 10000'
