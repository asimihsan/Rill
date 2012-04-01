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

import pymongo
import pymongo.binary
import database
from utilities import retry

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

# ----------------------------------------------------------------------------
#   Constants.
# ----------------------------------------------------------------------------
APP_NAME = "parser_tap_to_database"
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
#   Logging.
# ----------------------------------------------------------------------------
import logging
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)
# ----------------------------------------------------------------------------

def get_args():
    parser = argparse.ArgumentParser("Subscribe to ZeroMQ stream of logs, push them into a database.")
    parser.add_argument("--results",
                        dest="results_zeromq_binding",
                        metavar="ZEROMQ_BINDING",
                        required=True,
                        help="ZeroMQ binding we SUBSCRIBE to for results.")
    parser.add_argument("--collection",
                        dest="collection",
                        metavar="NAME",
                        default=None,
                        help="MongoDB collection name")
    parser.add_argument("--verbose",
                        dest="verbose",
                        action='store_true',
                        default=False,
                        help="Enable verbose debug mode.")
    args = parser.parse_args()
    return args

@retry()
def setup_database(args):
    collection = None
    if args.collection:
        db = database.Database()
        collection_name = args.collection
        collection = db.get_collection(collection_name)
        #for field in fields_to_index:
        #    db.create_index(collection_name, field)
    return collection

required_fields = ["contents", "year", "month", "day", "hour", "minute", "second"]
def validate_command(command):
    if not all(field in command for field in required_fields):
        return False
    return True

def main():
    args = get_args()
    logger = logging.getLogger("%s.%s" % (APP_NAME, args.collection))
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")
    logger.debug("entry.")
    collection = setup_database(args)

    context = zmq.Context(1)

    # ------------------------------------------------------------------------
    #   Subscribing to the parsed logs from a parser.
    # ------------------------------------------------------------------------
    logger.debug("Subscribing to parser at: %s" % (args.results_zeromq_binding, ))
    subscription_socket = context.socket(zmq.SUB)
    subscription_socket.connect(args.results_zeromq_binding)
    subscription_socket.setsockopt(zmq.SUBSCRIBE, "")
    subscription_socket.setsockopt(zmq.HWM, 100000) # only allow 100,000 messages into in-memory queue
    #subscription_socket.setsockopt(zmq.SWAP, 100 * 1024 * 1024) # offload 100MB of messages onto disk
    # ------------------------------------------------------------------------

    try:
        while 1:
            incoming_string = subscription_socket.recv()
            logger.debug("Update: '%s'" % (incoming_string, ))
            try:
                incoming_object = json.loads(incoming_string)
            except:
                logger.exception("Can't decode command:\n%s" % (incoming_string, ))
                continue
            if not validate_command(incoming_object):
                logger.error("Not a valid command: \n%s" % (incoming_object))
                continue

            # --------------------------------------------------------
            # Re-process the dict to get a real datetime object.
            # --------------------------------------------------------
            datetime_obj = datetime.datetime(int(incoming_object["year"]),
                                             int(incoming_object["month"]),
                                             int(incoming_object["day"]),
                                             int(incoming_object["hour"]),
                                             int(incoming_object["minute"]),
                                             int(incoming_object["second"]))
            data_to_store = incoming_object.copy()
            for key in ["year", "month", "day", "hour", "minute", "second"]:
                data_to_store.pop(key)
            data_to_store["datetime"] = datetime_obj
            # --------------------------------------------------------

            insert_into_collection(collection, data_to_store)
    except KeyboardInterrupt:
        logger.debug("CTRL-C")
    finally:
        logger.debug("exiting")

@retry()
def insert_into_collection(collection, data):
    collection.insert(data)

if __name__ == "__main__":
    main()

