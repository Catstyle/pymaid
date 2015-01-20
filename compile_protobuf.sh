#!/bin/sh

pwd=`pwd`
echo 'current path' $pwd
for proto in `find . -name '*.proto'`
do
    proto="$pwd/$proto"
    echo 'compiling' $proto
    protoc --python_out=$pwd --proto_path=$pwd $proto
done
