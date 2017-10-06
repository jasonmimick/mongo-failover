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

var getPrimaryOptime = function() {
    var status = admin.runCommand( { "replSetGetStatus" : 1 } );
    var pStatus = status.members.filter(m=>m.stateStr=="PRIMARY")
    if (pStatus.length==0) {
        throw "ERROR: No PRIMARY detected, retry recovery when PRIMARY available";
    }
    var primaryOptime = pStatus.pop().optimeDate;
    return primaryOptime;
}
var getHostOptime = function(host) {
    var status = admin.runCommand( { "replSetGetStatus" : 1 } );
    var hStatus = status.members.filter(m=>m.name==host)
    if (hStatus.length==0) {
        throw "ERROR: host "+host+" no found, retry recovery when "+host+" available";
    }
    var hostOptime = hStatus.pop().optimeDate;
    return hostOptime;
}

var allCaughtUp = function(cu) {
    return cu.every( c => c );
}
print("Waiting for dc-1 nodes to get caught up");
var caughtUp = [];
var catchUpSleep = 5000;

for (var i=0;i<dc1Ports.length;i++) {
    caughtUp.push(false);
}
while ( !allCaughtUp(caughtUp) ) {
    var pot = getPrimaryOptime();
    for (var i=0;i<dc1Ports.length;i++) {
        // skip nodes which already caught up
        if ( caughtUp[i] ) {
            continue;
        }
        var h =hostname()+":"+dc1Ports[i];
        var ht = getHostOptime(h);
        var lagSecs = (pot-ht)/1000;
        print("host " + h + " lag behind primary is " + lagSecs + "seconds.");
        if (lagSecs == 0) {
            caughtUp[i]=true;
        }
    }
    sleep(catchUpSleep);
}

var conf = admin.runCommand( { "replSetGetConfig": 1 } );

var fixedMembers = [];
dc1Ports.forEach( dcp => {
    var m = conf.config.members.filter( m => m.host==hostname()+":"+dcp).pop();
    m.priority=1;
    m.votes=1;
    fixedMembers.push(m);
});

dc2Ports.forEach( dcp => {
    var m = conf.config.members.filter( m => m.host==hostname()+":"+dcp).pop();
    fixedMembers.push(m);
});


conf.config.members = fixedMembers;
printjson(conf.config);

var result= admin.runCommand( { "replSetReconfig": conf.config, force : true } );
printjson(result);


