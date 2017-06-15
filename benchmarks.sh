#! /bin/bash
export PYTHONPATH=.:$PYTHONPATH

echo
name='chat'
echo 'checking '${name}', clients: 10, request/client: 100'
python -O examples/$name/server.py > /dev/null 2>&1 &
sid=$!
sleep 0.2
time python -O examples/$name/client.py -c 10 -r 100 > /dev/null 2>&1
disown -r
kill $sid
echo 'done '${name}', clients: 10, request/client: 100'

echo
name='echo'
echo 'checking '${name}', clients: 100, request/client: 100'
python -O examples/$name/server.py > /dev/null 2>&1 &
sid=$!
sleep 0.2
time python -O examples/$name/client.py -c 100 -r 100 > /dev/null 2>&1
echo 'done '${name}', clients: 100, request/client: 100'

echo
echo 'checking '${name}', clients: 100, request/client: 1000'
time python -O examples/$name/client.py -c 100 -r 1000 > /dev/null 2>&1
disown -r
kill $sid
echo 'done '${name}', clients: 100, request/client: 1000'

echo
name='heartbeat'
echo 'checking '${name}', clients: 1000'
python -O examples/$name/server.py > /dev/null 2>&1 &
sid=$!
sleep 0.2
time python -O examples/$name/client.py -c 1000 -s 5 > /dev/null 2>&1
disown -r
kill $sid
echo 'done '${name}', clients: 1000, sleep_time: 5'

echo
name='hello'
echo 'checking '${name}', clients: 100, request/client: 100'
python -O examples/$name/server.py > /dev/null 2>&1 &
sid=$!
sleep 0.2
time python -O examples/$name/client.py -c 100 -r 100 > /dev/null 2>&1
echo 'done '${name}', clients: 100, request/client: 100'

echo
echo 'checking '${name}', clients: 100, request/client: 1000'
time python -O examples/$name/client.py -c 100 -r 1000 > /dev/null 2>&1
disown -r
kill $sid
echo 'done '${name}', clients: 100, request/client: 1000'

echo
name='hello_pb'
echo 'checking '${name}', clients: 100, request/client: 100'
python -O examples/$name/server.py > /dev/null 2>&1 &
sid=$!
sleep 0.2
time python -O examples/$name/client.py -c 100 -r 100 > /dev/null 2>&1
echo 'done '${name}', clients: 100, request/client: 100'

echo
echo 'checking '${name}', clients: 100, request/client: 1000'
time python -O examples/$name/client.py -c 100 -r 1000 > /dev/null 2>&1
disown -r
kill $sid
echo 'done '${name}', clients: 100, request/client: 1000'

echo
name='reraise'
echo 'checking '${name}', clients: 100, request/client: 100'
python -O examples/$name/server.py > /dev/null 2>&1 &
sid=$!
time python -O examples/$name/client.py -c 100 -r 100 > /dev/null 2>&1
disown -r
kill $sid
echo 'done '${name}', clients: 100, request/client: 100'
