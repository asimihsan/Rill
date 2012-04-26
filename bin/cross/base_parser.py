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

from whoosh.analysis import FancyAnalyzer
from whoosh.analysis import StemmingAnalyzer
from whoosh.analysis import StandardAnalyzer
from whoosh.analysis import LowercaseFilter
from whoosh.analysis import RegexTokenizer
from whoosh.analysis import StopFilter

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

import logging
global APP_NAME
APP_NAME = "base_parser"

def get_args():
    parser = argparse.ArgumentParser("Parse incoming ZeroMQ stream of logs, output in another ZeroMQ stream.")
    parser.add_argument("--ssh_tap",
                        dest="ssh_tap_zeromq_binding",
                        metavar="ZEROMQ_BINDING",
                        required=True,
                        help="ZeroMQ binding we use for the ssh_tap instance.")
    parser.add_argument("--results",
                        dest="results_zeromq_binding",
                        metavar="ZEROMQ_BINDING",
                        required=True,
                        help="ZeroMQ binding we PUBLISH our results to.")
    parser.add_argument("--verbose",
                        dest="verbose",
                        action='store_true',
                        default=False,
                        help="Enable verbose debug mode.")
    args = parser.parse_args()
    return args

re_line_breaks = re.compile("(\r\n|\n)", re.DOTALL)
line_breaks = set(["\r\n", "\n"])
def split_contents_and_return_excess(contents):
    """ Given a block of text in contents split it into lines, and
    return a two-element tuple (elem1, elem2).
    -   elem1: list of strings for lines in the contents. If there
        are no full lines return an empty list.
    -   elem2: string of the excess, i.e. the last line.i

    We want to strip out blank lines.

    Examples below:

    contents = ""
    return ([], "")

    contents = "12345"
    return ([], "12345")

    contents = "12345\r"
    return ([], "12345\r")

    contents = "12345\r\n"
    return (["12345", ""])

    contents = "12345\n"
    return (["12345", ""])

    contents = "12345\n123456\n123457"
    return (["12345", "123456"], "1234567")

    contents = "\r\n\r\n\r\n12345"
    return ([], "12345")

    """

    logger = logging.getLogger("%s.split_contents_and_return_excess" % (APP_NAME, ))
    elems = re_line_breaks.split(contents)
    last_index = len(elems) - 1
    non_line_break_elems = [(i, elem) for (i, elem) in enumerate(elems)
                            if elem not in line_breaks]
    full_lines = [elem for (i, elem) in non_line_break_elems
                  if len(elem) != 0 and i != last_index]
    trailing_excess = elems[-1]

    return_value = (full_lines, trailing_excess)
    logger.debug("returning : %s" % (return_value, ))
    return return_value

def get_log_data_and_excess_lines(full_lines, log_datum_class):
    """ Given a list of strings corresponding to full lines from log output
    return a two-element tuple (elem1, elem2).
    - elem1: a list of zero or more LogDatum objects that correspond to the
    contents of the logs.
    - elem2: a list of lines that constitute a partial log datum.

    We will silently drop input that doesn't meet the spec of a log block."""

    logger = logging.getLogger("%s.get_log_data_and_excess_lines" % (APP_NAME, ))
    return_value = []
    for line in full_lines:
        log_datum = log_datum_class(line)
        return_value.append(log_datum)
    return (return_value, [])

required_fields = ["contents"]
def validate_command(command):
    if not all(field in command for field in required_fields):
        return False
    return True

def main(app_name, log_datum_class, fields_to_index):
    APP_NAME = app_name
    import logging
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    args = get_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")
    logger.debug("entry. log_datum_class: %s" % (log_datum_class, ))

    context = zmq.Context(1)

    # ------------------------------------------------------------------------
    #   Subscribing to the raw ssh_tap from a server.
    # ------------------------------------------------------------------------
    logger.debug("Subscribing to ssh_tap at: %s" % (args.ssh_tap_zeromq_binding, ))
    subscription_socket = context.socket(zmq.SUB)
    subscription_socket.setsockopt(zmq.SUBSCRIBE, "")
    subscription_socket.setsockopt(zmq.HWM, 1000) # only allow 1000 messages into in-memory queue
    subscription_socket.setsockopt(zmq.SWAP, 500 * 1024 * 1024) # offload 500MB of messages onto disk
    subscription_socket.connect(args.ssh_tap_zeromq_binding)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Publishing JSON for parsed log data.
    # ------------------------------------------------------------------------
    logger.debug("Publishing parsed results at: %s" % (args.results_zeromq_binding, ))
    publish_socket = context.socket(zmq.PUB)
    publish_socket.setsockopt(zmq.HWM, 1000) # only allow 1000 messages into in-memory queue
    publish_socket.setsockopt(zmq.SWAP, 500 * 1024 * 1024) # offload 500MB of messages onto disk
    publish_socket.bind(args.results_zeromq_binding)
    # ------------------------------------------------------------------------

    trailing_excess = ""
    full_lines = []
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
            assert("contents" in incoming_object)
            trailing_excess = ''.join([trailing_excess, incoming_object["contents"]])
            (new_full_lines, trailing_excess) = split_contents_and_return_excess(trailing_excess)
            full_lines.extend(new_full_lines)
            logger.debug("full_lines:\n%s" % (pprint.pformat(full_lines), ))
            logger.debug("trailing_excess:\n%s" % (trailing_excess, ))

            # ----------------------------------------------------------------
            # We now have lots of full lines and some trailing excess. Since a
            # log datum may consist of more than one full line we perform a
            # similar operation to above. We pass all the full lines to a
            # function which will generate LogDatum object and return
            # "trailing excess" full lines.
            # ----------------------------------------------------------------
            (log_data, full_lines) = get_log_data_and_excess_lines(full_lines, log_datum_class)
            for log_datum in log_data:
                logger.debug("publishing:\n%r" % (log_datum, ))
                datum_dict = log_datum.get_dict_representation()
                if datum_dict is None:
                    logger.warning("log_datum not valid, skip.")
                    continue
                publish_socket.send(json.dumps(datum_dict))
            # ----------------------------------------------------------------
    except KeyboardInterrupt:
        logger.debug("CTRL-C")
    finally:
        logger.debug("exiting")

if __name__ == "__main__":
    logger.error("Not intended for direct execution, pass in a log_datum class to main().")
    sys.exit(1)

