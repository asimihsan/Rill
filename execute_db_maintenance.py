#!/usr/bin/env python2.7

import os
import sys
import pdb
import time

import fabric
from fabric.operations import sudo, run, put
import fabric.network
from fabric.api import settings

# -----------------------------------------------------------------------------
#   Constants.
# -----------------------------------------------------------------------------
KEY_FILENAME = r"/root/.ssh/id_rsa"
APP_NAME = "execute_db_maintenance"
LOG_FILENAME = r"/var/log/execute_db_maintenance.log"
USERNAME = "root"
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
#   Logging.
# -----------------------------------------------------------------------------
import logging
import logging.handlers
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=10*1024*1024, backupCount=10)
fh.setFormatter(formatter)
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)
# -----------------------------------------------------------------------------

commands = [ \
             "mongo admin --eval \"printjson(db.adminCommand({replSetStepDown : 60}))\"",
             "sleep 60",
             "service mongod stop",
             "pkill -9 mongod",
             "numactl --interleave=all mongod --dbpath /var/lib/mongo --repair < /dev/null &> /dev/null",
             "chown -R mongod:mongod /var/lib/mongo",
             "service mongod start",
             ]
hosts = ["magpie", "rat", "fox", "rabbit"]

def main():
    logger = logging.getLogger("%s.main" % (APP_NAME, ))
    for host in hosts:
        logger.debug("working on host: %s" % (host, ))
        with settings(host_string = host,
                      user = USERNAME,
                      key_filename = KEY_FILENAME,
                      warn_only = True):
            for command in commands:
                logger.debug("executing command: %s" % (command, ))
                run(command)

if __name__ == "__main__":
    logger.debug("entry. starting in 5 seconds...")
    time.sleep(5)
    try:
        main()
    except:
        logger.exception("unhandled exception")
        sys.exit(1)

