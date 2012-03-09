#!/usr/bin/env python2.7

# ---------------------------------------------------------------------------
# Copyright (c) 2011 Asim Ihsan (asim dot ihsan at gmail dot com)
# Distributed under the MIT/X11 software license, see the accompanying
# file license.txt or http://www.opensource.org/licenses/mit-license.php.
# ---------------------------------------------------------------------------

import os
import sys
import zmq
import pprint
import datetime
import re
import json
import platform
import argparse

# !!AI hacks
import database

APP_NAME = "masspinger_tap"
import logging
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

# ----------------------------------------------------------------------------
#   Signal handling
# ----------------------------------------------------------------------------
import signal
def soft_handler(signum, frame):
    logging.debug('Soft stop')
    sys.exit(1)
def hard_handler(signum, frame):
    logging.debug('Hard stop')
    os._exit(2)
signal.signal(signal.SIGINT, soft_handler)
signal.signal(signal.SIGTERM, hard_handler)
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    logger.debug("starting")

    parser = argparse.ArgumentParser("Parse incoming ZeroMQ stream of masspinger data, shove into MongoDB.")
    parser.add_argument("--masspinger_zeromq_bind",
                        dest="masspinger_zeromq_bind",
                        metavar="ZEROMQ_BINDING",
                        required=True,
                        help="ZeroMQ binding we use for the masspinger instance.")
    parser.add_argument("--database",
                        dest="database",
                        metavar="NAME",
                        default=None,
                        help="MongoDB database name")
    parser.add_argument("--verbose",
                        dest="verbose",
                        action='store_true',
                        default=False,
                        help="Enable verbose debug mode.")
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")
    logger = logging.getLogger("%s" % (APP_NAME, ))
    context = zmq.Context(1)

    # ------------------------------------------------------------------------
    #   Subscribing to the raw masspinger output.
    # ------------------------------------------------------------------------
    logger.debug("Subscribing to masspinger at: %s" % (args.masspinger_zeromq_bind, ))
    subscription_socket = context.socket(zmq.SUB)
    subscription_socket.connect(args.masspinger_zeromq_bind)
    subscription_socket.setsockopt(zmq.SUBSCRIBE, "")
    # ------------------------------------------------------------------------

    if args.database:
        db = database.Database(args.database)
    try:
        while 1:
            #logger.debug("tick")
            incoming = subscription_socket.recv_multipart()
            if len(incoming) != 2:
                logger.warning("Invalid message from masspinger: %s" % (incoming, ))
                continue
            (hostname, state) = incoming
            if platform.system() == "Linux":
                logger.debug("Put it into the DB.")
                datetime_obj = datetime.datetime.utcnow()
                data_to_store = {"datetime": datetime_obj,
                                 "hostname": hostname,
                                 "responsive": state == "responsive"}
                collection_name = "%s_pings" % (hostname, )
                collection = db.get_collection(collection_name)
                db.ensure_index(collection_name, "datetime")
                #db.ensure_index(collection_name, "hostname", index_type = None)
                logger.debug("Putting: %s" % (data_to_store, ))
                collection.insert(data_to_store)
            # ----------------------------------------------------------------
    except KeyboardInterrupt:
        logger.debug("CTRL-C")
    finally:
        logger.debug("exiting")
