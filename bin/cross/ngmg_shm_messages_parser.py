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

from whoosh.analysis import FancyAnalyzer
from whoosh.analysis import StemmingAnalyzer
from whoosh.analysis import StandardAnalyzer
from whoosh.analysis import LowercaseFilter
from whoosh.analysis import RegexTokenizer
from whoosh.analysis import StopFilter

APP_NAME = "ngmg_shm_messages_parser"
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

# Feb 26 23:41:29 emer_mf106-wrlinux daemon.notice SYSSTAT(MSMonitor30)[3488]: report status: success: STATUS_OK @MSMonitor30, code=253, severity=0
class LogDatum(object):
    def __init__(self, string_input):
        self.string_input = string_input

    # ------------------------------------------------------------------------
    #   Format of the datetime at the start of the line.
    # ------------------------------------------------------------------------
    DATETIME_FORMAT = "%Y %b %d %H:%M:%S"
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Regular expression to get elements out of the line.
    # ------------------------------------------------------------------------
    re1='((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Sept|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?))'  # Month 1
    re2='.*?' # Non-greedy match on filler
    re3='((?:(?:[0-2]?\\d{1})|(?:[3][01]{1})))(?![\\d])'    # Day 1
    re4='.*?' # Non-greedy match on filler
    re5='((?:(?:[0-1][0-9])|(?:[2][0-3])|(?:[0-9])):(?:[0-5][0-9])(?::[0-5][0-9])?(?:\\s?(?:am|AM|pm|PM))?)'    # HourMinuteSec 1
    re6='.*?' # Non-greedy match on filler
    re7='((?:[a-z][a-z\\.\\d\\-]+)\\.(?:[a-z][a-z\\-]+))(?![\\w\\.])' # Fully Qualified Domain Name 1
    re8='(.*)' # Rest of the line
    RE_LINE = re.compile(re1+re2+re3+re4+re5+re6+re7+re8, re.IGNORECASE | re.DOTALL)
    # ------------------------------------------------------------------------

    def get_dict_representation(self):
        """ Given a block of a full log event return a dict with the following
        required keys:
        -   year: integer
        -   month: integer
        -   day: integer
        -   hour: integer
        -   minute: integer
        -   second: integer
        -   contents: full block from the log.

        and the following optional keys:
        -   microsecond: integer

        Add whatever other keys you like for subscribers to this parser. The
        most relevent is "_keywords", which we prepare for MongoDB consumers
        so that we get to decide how they tokenize the string in preparation
        for full-text searching.

        Example lines:

        2012-Feb-25 19:36:44 testvm.2 green a a a a a a a a a a a a a
        2012-Feb-25 19:36:43 testvm.2 a a a a a a a a a a a a a i am a lion watch me roar

        - If the log outputs data in single lines contents will always be a single line.
        - If the log outputs data to multiple lines for a given datetime contents may
        be a line-delimited string.

        Return None if the input can't be parsed.
        """

        if len(self.string_input.splitlines()) != 1:
            return None
        m = self.RE_LINE.search(self.string_input)
        if not m:
            return None
        year = str(datetime.datetime.now().year)
        month1 = m.group(1)
        day1 = m.group(2)
        time1 = m.group(3)
        fqdn = m.group(4)
        contents = m.group(5)

        full_datetime = " ".join([year, month1, day1, time1])
        try:
            datetime_obj = datetime.datetime.strptime(full_datetime, self.DATETIME_FORMAT)
        except ValueError:
            return None
        return_value = {}
        return_value["year"] = str(datetime_obj.year)
        return_value["month"] = str(datetime_obj.month)
        return_value["day"] = str(datetime_obj.day)
        return_value["hour"] = str(datetime_obj.hour)
        return_value["minute"] = str(datetime_obj.minute)
        return_value["second"] = str(datetime_obj.second)
        return_value["contents"] = self.string_input
        return_value["_keywords"] = self.tokenize(return_value["contents"])
        return return_value

    analyzer = StandardAnalyzer()
    def tokenize(self, input):
        """Given a blob of input prepare a list of strings that is suitable
        for full-text indexing by MongoDB.

        I'm going to cheat and use Whoosh."""

        m = self.RE_LINE.search(self.string_input)
        if not m:
            return []
        contents = m.group(5)
        tokens = []
        for elem in self.analyzer(contents):
            if hasattr(elem, "pos"):
                tokens.append((elem.text, elem.pos))
            else:
                tokens.append((elem.text, None))
        unique_tokens = list(set([text for (text, pos) in tokens]))
        return sorted(unique_tokens)

    def __repr__(self):
        return "LogDatum: %s" % (self.get_dict_representation(), )

    def __str__(self):
        return "%s" % (self.get_dict_representation(), )

def validate_command(command):
    if "contents" not in command:
        return False
    return True

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

def get_log_data_and_excess_lines(full_lines):
    """ Given a list of strings corresponding to full lines from log output
    return a two-element tuple (elem1, elem2).
    - elem1: a list of zero or more LogDatum objects that correspond to the
    contents of the logs.
    - elem2: a list of lines that constitute a partial log datum.

    We will silently drop input that doesn't meet the spec of a log block."""

    logger = logging.getLogger("%s.get_log_data_and_excess_lines" % (APP_NAME, ))
    return_value = []
    for line in full_lines:
        log_datum = LogDatum(line)
        return_value.append(log_datum)
    return (return_value, [])

if __name__ == "__main__":
    logger.debug("starting")

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
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")
    logger = logging.getLogger("%s.%s" % (APP_NAME, args.collection))
    context = zmq.Context(2)

    # ------------------------------------------------------------------------
    #   Subscribing to the raw ssh_tap from a server.
    # ------------------------------------------------------------------------
    logger.debug("Subscribing to ssh_tap at: %s" % (args.ssh_tap_zeromq_binding, ))
    subscription_socket = context.socket(zmq.SUB)
    subscription_socket.connect(args.ssh_tap_zeromq_binding)
    subscription_socket.setsockopt(zmq.SUBSCRIBE, "")
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Publishing JSON for parsed log data.
    # ------------------------------------------------------------------------
    logger.debug("Publishing parsed results at: %s" % (args.results_zeromq_binding, ))
    publish_socket = context.socket(zmq.PUB)
    publish_socket.connect(args.results_zeromq_binding)
    # ------------------------------------------------------------------------

    #poller = zmq.Poller()
    #poller.register(subscription_socket, zmq.POLLIN)
    #poll_interval = 1000

    trailing_excess = ""
    full_lines = []

    # !!AI hacks
    if args.collection:
        db = database.Database()
        collection_name = args.collection
        collection = db.get_collection(collection_name)
        db.create_index(collection_name, "datetime")
        db.create_index(collection_name, "keywords")
    try:
        while 1:
            #socks = dict(poller.poll(poll_interval))
            #if socks.get(subscription_socket, None) != zmq.POLLIN:
            #    continue
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
            (log_data, full_lines) = get_log_data_and_excess_lines(full_lines)
            for log_datum in log_data:
                logger.debug("publishing:\n%r" % (log_datum, ))
                publish_socket.send(str(log_datum))

                # !!AI hacks
                # I can't figure out what I can't get thie data off the
                # publish socket. So screw it, let's put it into the database
                # right now.
                if platform.system() == "Linux":
                    logger.debug("!!AI hacks, just put it into the DB.")
                    log_dict = log_datum.get_dict_representation()
                    datetime_obj = datetime.datetime(int(log_dict["year"]),
                                                     int(log_dict["month"]),
                                                     int(log_dict["day"]),
                                                     int(log_dict["hour"]),
                                                     int(log_dict["minute"]),
                                                     int(log_dict["second"]))
                    contents = log_dict["contents"]
                    keywords = log_dict["_keywords"]
                    data_to_store = {"datetime": datetime_obj,
                                     "contents": contents,
                                     "keywords": keywords}
                    collection.insert(data_to_store)
            # ----------------------------------------------------------------
    except KeyboardInterrupt:
        logger.debug("CTRL-C")
    finally:
        logger.debug("exiting")
