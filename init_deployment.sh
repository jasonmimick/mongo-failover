#!/bin/bash

# init_deployment.sh
# create a 3+2 replica-set
# we will simulate data centers with different
# directories for dbpath's

BASE_PORT=28000
REPLSET=FooBar
WRITE_CONCERN={w:majority}
#set -e
rm -rf {dc-1,dc-2}

mkdir {dc-1,dc-2}

MONGO_VERSION=`m available --stable | grep '3.2.' | head -1 | awk '{print $2}' | strings`
echo "using MongoDB version $MONGO_VERSION"
echo "m use $MONGO_VERSION --enterprise"
m use $MONGO_VERSION --enterprise
# dc-1
cd dc-1
mkdir {rs-1,rs-2,rs-3}
mongod --fork --replSet $REPLSET --port $((BASE_PORT)) --logpath ./rs-1/mongod.log --dbpath ./rs-1
mongod --fork --replSet $REPLSET --port $((BASE_PORT+1)) --logpath ./rs-2/mongod.log  --dbpath ./rs-2
mongod --fork --replSet $REPLSET --port $((BASE_PORT+2)) --logpath ./rs-3/mongod.log --dbpath ./rs-3

cd ../dc-2
mkdir {rs-4,rs-5}
mongod --fork --replSet $REPLSET --port $((BASE_PORT+3)) --logpath ./rs-4/mongod.log --dbpath ./rs-4
mongod --fork --replSet $REPLSET --port $((BASE_PORT+4)) --logpath ./rs-5/mongod.log --dbpath ./rs-5

cd ..
mongo --port $BASE_PORT --eval 'rs.initiate()' --quiet
echo "Initializing replica set"; sleep 2
echo "Configuring replica set"
for I in 1 2 3 4; do
    P=$((BASE_PORT+I))
    echo "Adding `hostname -f`:$P"
    mongo --port $BASE_PORT --eval "rs.add(hostname()+\":$P\")"
    sleep 1
done
echo "Replica set configured"

cd dc-2
echo "Launching arbiter - not adding to replia set"
mkdir arbiter
ARBITER_PORT=$((BASE_PORT+10))
mongod --fork --replSet $REPLSET --port $ARBITER_PORT \
--logpath ./arbiter/mongod.log --dbpath ./arbiter

cd ..

CONN_STR="mongodb://localhost:$BASE_PORT,localhost:$((BASE_PORT+1)),\
localhost:$((BASE_PORT+2)),localhost:$((BASE_PORT+3)),localhost:$((BASE_PORT+4))/\
test?replicaSet=$REPLSET"

echo "testing writes to $CONN_STR with write concern $WRITE_CONCERN"
mongo $CONN_STR --eval 'var wr=db.foo.insert({a:1},{w:"majority"});printjson(wr);' --quiet

echo "simulating dc-1 outage, by stopping all nodes in dc-1"
for DBPATH in rs-1 rs-2 rs-3; do
    echo "stopping dc1 node $DBPATH"
    PID="$(ps -ef | grep mongod | grep $DBPATH | awk '{print $2}')"
    kill $PID
    sleep 2
done

echo "validating only 2 nodes alive"
if ! [ `ps -ef | grep mongod | grep 'rs-' | wc -l` == 2 ]; then
    echo "did not detect 2 nodes alive, simluation ending"
    exit 1
fi

echo "testing insert with {w:\"majority\",wtimeout:2000} should fail"
mongo $CONN_STR \
--eval 'var wr=db.foo.insert({a:1},{w:"majority","wtimeout":2000});printjson(wr);' \
--quiet

echo "Start failover procedure: add arbiter, and set votes=0 for dc-1 nodes"
mongo --nodb ./failover.js

echo "testing writes work again by inserting a document"
echo "to $CONN_STR with write concern $WRITE_CONCERN"
mongo $CONN_STR --eval 'var wr=db.foo.insert({a:1},{w:"majority"});printjson(wr);' --quiet

echo "Restarting dc-1 nodes"
cd dc-1
mongod --fork --replSet $REPLSET --port $((BASE_PORT)) --logpath ./rs-1/mongod.log --dbpath ./rs-1
mongod --fork --replSet $REPLSET --port $((BASE_PORT+1)) --logpath ./rs-2/mongod.log  --dbpath ./rs-2
mongod --fork --replSet $REPLSET --port $((BASE_PORT+2)) --logpath ./rs-3/mongod.log --dbpath ./rs-3
cd ..
sleep 3

echo "Start recovery script"
mongo --nodb ./recovery.js

echo "testing writes work again by inserting a document"
echo "to $CONN_STR with write concern $WRITE_CONCERN"
mongo $CONN_STR --eval 'var wr=db.foo.insert({a:1},{w:"majority"});printjson(wr);' --quiet



