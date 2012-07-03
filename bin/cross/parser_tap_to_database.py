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
import heapq
import gc

import pymongo
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
def setup_database(collection_name):
    collection = None
    db = database.Database()
    collection = db.get_collection(collection_name)
    collection.ensure_index("contents_hash",
                            unique=True,
                            drop_dups=True,
                            background=True)
    collection.ensure_index([("datetime", -1)],
                             background=True)
    fields_to_index = [ \
                       "keywords",
                       "failure_type",
                       "failure_id",
                       "error_level",
                       "error_id",
                      ]
    for field in fields_to_index:
        try:
            index_param = [(field, 1), ("datetime", 1)]
            collection.ensure_index(index_param, background=True)
        except pymongo.errors.OperationFailure:
            logger.exception("Exception when requesting index build. Not a disaster.")
            continue
    return collection

required_fields = ["contents", "year", "month", "day", "hour", "minute", "second"]
def validate_command(command):
    if not all(field in command for field in required_fields):
        return False
    return True

def main():
    args = get_args()
    collection_name = args.collection
    logger = logging.getLogger("%s.%s" % (APP_NAME, collection_name))
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")
    logger.debug("entry.")
    collection = setup_database(collection_name)

    context = zmq.Context(1)

    # ------------------------------------------------------------------------
    #   Subscribing to the parsed logs from a parser.
    # ------------------------------------------------------------------------
    logger.debug("Subscribing to parser at: %s" % (args.results_zeromq_binding, ))
    subscription_socket = context.socket(zmq.SUB)
    subscription_socket.setsockopt(zmq.SUBSCRIBE, "")
    subscription_socket.setsockopt(zmq.HWM, 1000) # only allow 1000 messages into in-memory queue
    subscription_socket.setsockopt(zmq.SWAP, 10 * 1024 * 1024) # offload 10MB of messages onto disk
    subscription_socket.connect(args.results_zeromq_binding)
    # ------------------------------------------------------------------------

    poller = zmq.Poller()
    poller.register(subscription_socket, zmq.POLLIN)
    poll_interval = 1000
    parser_accumulator = []
    try:
        while 1:
            socks = dict(poller.poll(poll_interval))
            parser_accumulator = send_old_parser_socket_data(collection_name, collection, parser_accumulator)
            if socks.get(subscription_socket, None) == zmq.POLLIN:
                parser_accumulator = handle_parser_socket_activity(subscription_socket, collection_name, collection, parser_accumulator)

    except KeyboardInterrupt:
        logger.debug("CTRL-C")
    finally:
        logger.debug("exiting")

# --------------------------------------------------------
#   Insert data once a minute. The reads kill the
#   database because of how fast and constant they are
#   so batch up both the reads to determine if the logs
#   already exist and the insertion.
#
#   Do this by maintaining a heap of logs. Logs are
#   stored as (datetime_received, log_data). Hence
#   the smallest element of the heap, accessible as O(1),
#   is the oldest log received. If the oldest log received
#   is more than 'insert_interval' old insert up to
#   'chunk_size' elements of the heap.
#
#   Irregardless of when logs are received if we have
#   more than 'chunk_size' in the heap insert them now;
#   you're going to run into MongoDB's 16MB query limit
#   if you don't. (16*1024 / 10000 ~= 1.6KB, safe).
# --------------------------------------------------------
def send_old_parser_socket_data(collection_name, collection, parser_accumulator):
    logger = logging.getLogger("%s.%s.send_old_parser_socket_data" % (APP_NAME, collection_name))
    datetime_now = datetime.datetime.utcnow()
    insert_interval = datetime.timedelta(minutes=1)

    if len(parser_accumulator) == 0:
        return parser_accumulator
    # The accumulator isn't full, so flush in chunk
    # pieces every interval.
    smallest_element = heapq.nsmallest(1, parser_accumulator)[0]
    smallest_datetime = smallest_element[0]
    logger.debug("smallest interval: %s" % (datetime_now - smallest_datetime, ))
    if (datetime_now - smallest_datetime) < insert_interval:
        return parser_accumulator

    # The oldest log is older than 'insert_interval'.
    logger.debug("oldest log is too old")
    chunk_size = 10000
    data_to_insert = []
    while len(parser_accumulator) > 0 and len(data_to_insert) <= chunk_size:
        datum = heapq.heappop(parser_accumulator)[1]
        data_to_insert.append(datum)
    if len(data_to_insert) > 0:
        logger.debug("inserting %s rows, some may be dupes." % (len(data_to_insert), ))
        insert_into_collection(collection, data_to_insert)
        gc.collect()
    return parser_accumulator

def handle_parser_socket_activity(subscription_socket, collection_name, collection, parser_accumulator):
    logger = logging.getLogger("%s.%s.handle_parser_socket_activity" % (APP_NAME, collection_name))
    incoming_string = subscription_socket.recv()
    try:
        incoming_object = json.loads(incoming_string)
    except:
        logger.exception("Can't decode command:\n%s" % (incoming_string, ))
        return parser_accumulator
    if not validate_command(incoming_object):
        logger.error("Not a valid command: \n%s" % (incoming_object))
        return parser_accumulator

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

    chunk_size = 10000
    heapq.heappush(parser_accumulator, (datetime.datetime.utcnow(), data_to_store))
    data_to_insert = []

    if len(parser_accumulator) > chunk_size:
        # The accumulator exceeds the chunk size. Flush
        # in chunk_size pieces.
        for i in xrange(chunk_size):
            datum = heapq.heappop(parser_accumulator)[1]
            data_to_insert.append(datum)
    if len(data_to_insert) > 0:
        logger.debug("inserting %s rows, some may be dupes." % (len(data_to_insert), ))
        insert_into_collection(collection, data_to_insert)
        gc.collect()
    # --------------------------------------------------------

    if len(parser_accumulator) % 1000 == 0:
        logger.debug("returning parser_accumulator of length: %s" % (len(parser_accumulator), ))
    return parser_accumulator

@retry()
def insert_into_collection(collection, data):
    collection.insert(data, continue_on_error=True)

if __name__ == "__main__":
    main()

