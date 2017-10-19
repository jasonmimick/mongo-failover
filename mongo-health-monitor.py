#!/usr/bin/env python
#
# Monitor a MongoDB replica set and take action
# if no PRIMARY node is detected.
#
# jason.mimick@mongodb.com
#
#python mongo-health.monitor.py --logpath /var/log/mongo-monitor.log \
#--mongodb mongodb://server1:27000,server2:27000,server3:27000/?replicaSet=prod \
#--action '{"action":"runScript", "script" : "/opt/failover.js" }'
#
# Supported actions - email,runScript
#
__version__ = "0.0.1"

import logging, argparse
import sys,os
import traceback
from time import sleep
import datetime
import pymongo, json
import smtplib
from email.mime.text import MIMEText
import socket
import subprocess

class App():

    def __init__(self, args, logger):
        self.args = args
        self.logger = logger

        self.action_map = { "email" : "action__email", "runScript" : "action__run_script" }
        self.logger.debug("self.args.action=%s" % self.args.action)
        self.action_args = json.loads(self.args.action)
        action = self.action_args['action']
        self.logger.debug("Found action='%s'" % action)
        if not action in self.action_map.keys():
            raise Exception("Unknown action '%s', cannot process" % action)
        self.logger.debug("action_args: %s" % str(self.action_args))

        # validate mongodb connection string

    def invoke(self):
        try:
            self.__monitor()
        except (KeyboardInterrupt, SystemExit):
            self.logger.info("Caught shutdown - monitoring stopping")

    # --- action's implemented here ---
    # actions should throw exceptions which bubble up
    # and end program
    # { 'action' : 'runScript', script : <script>, args : [ <array of addition args> ] }
    def action__run_script(self,ts):
        self.logger.info("__run_script ts=%s"%ts)
        script = self.action_args['script']
        args = self.action_args['args']
        if len(args)>0:
            s = args.insert(0,script)
            self.logger.debug("Calling %s with args %s" % (script,','.join(args)))
            ret = subprocess.check_call(s,shell=True)
        else:
            s = script
            self.logger.debug("Calling %s" % script)
            ret = subprocess.call(s,shell=True)
        self.logger.debug("ret = %s " % ret)


    def action__email(self,ts):
        self.logger.info("__action ts=%s"%ts)
        msg = MIMEText("mongo-health-monitor NO PRIMARY for %s" % self.args.mongodb)
        msg['Subject'] = "ALERT mongo-heath-monitor"
        to = self.action_args['to']
        sender = "mongo-health-monitor@%s" % socket.getfqdn()
        msg['From'] = sender
        msg['To'] = ",".join(to)
        s = smtplib.SMTP('localhost')
        self.logger.debug('sending "%s" to %s' % (msg.as_string(),to) )
        s.sendmail(sender, to, msg.as_string())
        s.quit()

    def __action(self,when):
        method = self.action_map[self.action_args['action']]
        self.logger.debug('method=%s'%method)
        action = getattr(self,method)
        action(when)

    def __monitor(self):
        healthy = True
        poll_count = 1
        while healthy:
            healthy = self.__check_if_primary()
            if healthy:
                self.logger.info( "HEALTHY check #%d" % poll_count )
                poll_count += 1
                sleep(self.args.pollSeconds)
        # if here, NOT HEALTHY
        self.__action(datetime.datetime.now())

    def __check_if_primary(self):
        try:
            mongo = pymongo.MongoClient( self.args.mongodb,
                                         readPreference='secondary',
                                         connectTimeoutMS=(self.args.pollSeconds*1000) )
            self.logger.debug("created mongo")
            rs_status = mongo.admin.command("replSetGetStatus",
                                            read_preference=pymongo.read_preferences.Secondary())
            self.logger.debug("ran replSetGetStatus")
            self.logger.debug("%s" % rs_status)
            #if rs_status['myState']==2:
            p = [m for m in rs_status['members'] if m['stateStr']=='PRIMARY']
            self.logger.debug("%s" % p)
            if not len(p)==1:
                self.logger.info("NOT HEALTHY no PRIMARY found")
                return False
            else:
                self.logger.info("HEALTHY Replica Set PRIMARY=%s" % p[0])
                return True
        except Exception as exp:
            self.logger.error(exp)
            return False

def main():
    # parse arguments
    description = u'mongo-health-monitor- Monitor replica set health'
    epilog = ('''mongo-health-monitor is a configurable daemon which will continuously
poll a MongoDB replica set and take action should no PRIMARY node be detected.
Pass a JSON document to the --action argument, example follows.
Possible --action's are:
	{ 'action' : 'email', to : [ <list of email addresses> ] },
	{ 'action' : 'runScript', script : <script>, args : [ <array of addition args> ] }

Example invocation:
$python mongo-health.monitor.py --logpath /var/log/mongo-monitor.log \
--mongodb mongodb://server1:27000,server2:27000,server3:27000/?replicaSet=prod \
--action '{"action":"runScript", "script" : "/opt/failover.js" }'

''')
    parser = argparse.ArgumentParser(description=description,epilog=epilog
                                     ,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version",action='store_true',default=False,help='print version and exit')
    parser.add_argument("--pretty",action='store_true',default=False,help='pretty format JSON')
    parser.add_argument("--loglevel",default='debug'
                         ,help='loglevel debug,info default=info')
    parser.add_argument("--logfile",default='--',help='logfile full path or -- for stdout')
    parser.add_argument("--mongodb",help='MongoDB connection string to replica set')
    parser.add_argument("--pollSeconds",default=10,help='How many seconds to wait between each poll')
    parser.add_argument("--action",help='Action to take when no PRIMARY node detected')

    args = parser.parse_args()
    if (args.version):
	print('mongo-health-monitor version: %s' % __version__ )
        os._exit(0)
    logger = logging.getLogger("mongo-health-monitor")
    logger.setLevel(getattr(logging,args.loglevel.upper()))
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s")
    if args.logfile == '--':
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = logging.FileHandler(os.path.abspath(args.logfile))
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.info(description)
    logger.info('version: %s' % __version__)
    logger.debug("args: " + str(args))
    logger.info("log level set to " + logging.getLevelName(logger.getEffectiveLevel()))
    required_args = [ 'mongodb', 'action' ]
    missing_args = []
    for arg in required_args:
        if getattr(args,arg) is None:
            missing_args.append(arg)
    if len(missing_args)>0:
        logger.error('error: missing required argument(s): %s' % ', '.join(missing_args))
        os._exit(1)

    app = App(args, logger)
    logger.info('mongo-health-monitor initialized')
    try:
        logger.info('running...')
        result = app.invoke()
        logger.info('mongo-health-monitor done')
        os._exit(0)
    except Exception as exp:
        logger.error(exp)
        logger.debug("got exception going to call sys.exit(1)")
        traceback.print_exc()
        os._exit(1)



if __name__ == '__main__':
    main()

