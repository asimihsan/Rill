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

APP_NAME = "ngmg_ms_messages_parser"
import logging
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

import base_parser

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

# Mar  7 19:38:33 alpheratz1 19:38:33.114 MS SI[20765]: [ID 452160 local1.info] Assertion (handled) failed: 'term_cb->pg.old_dsp_channel != TPC_TC_DSP_CHANNEL_UNASSIGNED', file ../../../msw/code/tpc/tpcpgc.c, line 3529.  Total handled asserts: 128
# Mar  6 15:50:17 subra2 MS craft: 06-Mar-2012, 15:50:17 UTC.  Craft user stopping the Integrated Softswitch

class NgmgMsMessagesParserLogDatum(object):
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
    re1='((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Sept|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?))' # Month 1
    re2='.*?' # Non-greedy match on filler
    re3='(\d+)' # Day number
    re4='.*?' # Non-greedy filler
    re5='((?:(?:[0-1][0-9])|(?:[2][0-3])|(?:[0-9])):(?:[0-5][0-9])(?::[0-5][0-9])?(?:\\s?(?:am|AM|pm|PM))?)'    # HourMinuteSec 1
    re6='.*?' # Non-greedy match on filler
    re7='((?:[a-z][a-z]+))' # Word 1a
    re8=' (.*)' # the rest
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
        hostname = m.group(4)
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
        return_value["keywords"] = self.tokenize(return_value["contents"])
        return_value = self.handle_ms_failures(return_value)
        return return_value

    def handle_ms_failures(self, current_return_value):
        if "contents" not in current_return_value:
            return current_return_value
        contents = current_return_value["contents"]

        if "failed: " in contents:
            elems = contents.partition("failed: ")
            failure_type = elems[0].strip().rsplit("]", 1)[-1].strip()
            failure_id = elems[-1].strip()
            if ".  Total" in failure_id:
                elems = failure_id.partition(".  Total")
                failure_id = elems[0]
            current_return_value["failure_type"] = failure_type
            current_return_value["failure_id"] = failure_id
            return current_return_value
        elif "Unhandled exception. " in contents:
            failure_string = contents.rsplit("]", 1)[-1].strip()
            elems = failure_string.split("Unhandled exception. ")
            failure_type = "Unhandled exception"
            failure_id = elems[-1].strip()
            current_return_value["failure_type"] = failure_type
            current_return_value["failure_id"] = failure_id
            return current_return_value
        else:
            return current_return_value

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

if __name__ == "__main__":
    logger.debug("starting")
    fields_to_index = ["datetime", "keywords", "failure_type", "failure_id"]
    try:
        base_parser.main(APP_NAME, NgmgMsMessagesParserLogDatum, fields_to_index)
    except KeyboardInterrupt:
        logger.debug("CTRL-C")
    finally:
        logger.debug("exiting")

