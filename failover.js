/*
 * failover.js
 *
 * Example script - DO NOT USE IN PRODUCTION
 *
 * Reconfigure replica set to
 * 1) Add arbiter
 * 2) Set priority=0 & votes=0 on dc-1 nodes
 *
 */

var portDC2Arbiter = 28010;
var dc1Ports = [ 28000,28001,28002 ];
var dc2Ports = [ 28003,28004 ];

print("Connecting to " + hostname()+":"+dc2Ports[0]);
var mongo = new Mongo(hostname()+":"+dc2Ports[0]);
var admin = mongo.getDB("admin");

// set 'db' var to admin so helper 'rs' object works
db = admin;


var conf = admin.runCommand( { "replSetGetConfig": 1 } );

var fixedMembers = [];
dc1Ports.forEach( dcp => {
    var m = conf.config.members.filter( m => m.host==hostname()+":"+dcp).pop();
    m.priority=0;
    m.votes=0;
    fixedMembers.push(m);
});

dc2Ports.forEach( dcp => {
    var m = conf.config.members.filter( m => m.host==hostname()+":"+dcp).pop();
    fixedMembers.push(m);
});

fixedMembers.push( {
    "_id" : 5,
    "host" : hostname() + ":" + portDC2Arbiter,
    "arbiterOnly" : true
});

conf.config.members = fixedMembers;
printjson(conf.config);

var result= admin.runCommand( { "replSetReconfig": conf.config, force : true } );
printjson(result);

print("Waiting for election to force new primary");
var gotPrimary = false;
var pcWait = 1000;
var pcCount = 0;
var maxpcCount = 30;
while ( !gotPrimary ) {
    var p = rs.status().members.filter(m=>m.stateStr=="PRIMARY");
    if ( p.length > 0 ) {
        print("New primary elected");
        printjson(p[0]);
        gotPrimary = true;
    } else {
        pcCount++;
        if ( pcCount >= maxpcCount ) {
            throw "ERROR: Unable to detect new primary after " + maxpcCount + " checks";
        }
        print("No primary detected, checking again after " + pcWait + "ms");
        sleep(pcWait);
    }
}

