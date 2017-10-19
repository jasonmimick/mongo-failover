
**DRAFT - NOT COMPLETE AND REVIEW - USE ONLY AS A SAMPLE
NEVER IN PRODUCTION**



This repository contains an 
example of semi-automated failover between 2 data centers for
a 5-node MongoDB replica set.

We assume a basic familiarity with MongoDB and replica set.
Please consult the MongoDB documentation to learn about these topics.

Ideally when deploying a highly-available MongoDB system
3 data centers are available. In this case, we can deploy a replica set
as follows.

| DC1 | DC2 | DC3 |
| --- | --- | --- |
| `P` | `S` | `S` |
| `S` | `S` |     |

Where `P` is the *Primary* node and the `S` stands for *Secondary* nodes.
With 5 members we need at least 3 node available to have a healthy system.
This means we can lose any 2 nodes *or* any one data center.

But, if we have the following setup;

| DC1 | DC2 |
| --- | --- |
| `P` | `S` |
| `S` | `S` |
| `S` |     |

We could still lose any 3 nodes, but we've lost the resliency to a data center loss.

In this case, there isn't (yet) any way to automatically failover but there is a 
*semi*-automated possible solution presented here.

The basic idea is to detect that the replica set is unhealthy and then 
temporarily reconfigure the system so that it can accept writes. Once things
are back to normal, we can then undo the configuration changes.

Here are the details. First, note that we're only conerned with automating the failover
to DC2 in this scenario since it's only when DC1 goes down that there are only 2
healthy nodes in the system. When this happens we can start a light weight 
MongoDB process running in *Arbiter* mode. An arbiter is a special member of a 
replica set which doesn't maintain a copy of data, but just exists to vote in elections.
We then reconfigure the replica set by adding the new arbiter and setting the 
`votes` attribute of the nodes in DC1 to 0. Now we effectively have a 3 node replica
set (since there are only 3 voting members of the 6 member replica set).






TODO - check for network partition!!! 



failover.js, can just invoke recovery.js right away
TODO: create wrapper which calls both, and that will be called
by health-monitor.py

