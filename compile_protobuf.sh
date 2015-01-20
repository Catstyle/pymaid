#!/bin/sh

pwd=`pwd`
echo 'current path' $pwd
for proto in `find $pwd -name '*.proto'`
do
    echo 'compiling' $proto
    protoc --python_out=$pwd --proto_path=$pwd $proto
done
