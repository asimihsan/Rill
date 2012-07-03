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
import hashlib
import base64

from whoosh.analysis import FancyAnalyzer
from whoosh.analysis import StemmingAnalyzer
from whoosh.analysis import StandardAnalyzer
from whoosh.analysis import LowercaseFilter
from whoosh.analysis import RegexTokenizer
from whoosh.analysis import StopFilter

APP_NAME = "ngmg_shm_hpilist_parser"
import logging
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

import base_parser
from ngmg_base_log_datum import NgmgBaseLogDatum

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

class NgmgShmHpilistParserLogDatum(NgmgBaseLogDatum):
    """ Block starts as:

    17-Apr-2012, 10:32:37.037 UTC

    """

    # ------------------------------------------------------------------------
    #   Format of the datetime at the start of the line.
    # ------------------------------------------------------------------------
    DATETIME_FORMAT = "%H:%M:%S"
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Regular expression to get elements out of the list of lines.
    # ------------------------------------------------------------------------
    re1 = "^(?P<time>\d{2}:\d{2}:\d{2})"
    re2 = "\.(?P<millisecond>\d{3})"
    re3 = ".*Source\s*:\s*.*"
    RE_BLOCK_START = re.compile(re1+re2+re3, re.IGNORECASE | re.DOTALL)

    RE_SOURCE = re.compile(".*Source\s*:\s*(?P<source>\d+)", re.IGNORECASE | re.DOTALL)
    RE_EVENT_TYPE = re.compile(".*EventType\s*:\s*(?P<event_type>.*)", re.IGNORECASE | re.DOTALL)
    RE_COMPONENT_PATH = re.compile(".*?(?P<component_path>\{.*\})", re.IGNORECASE | re.DOTALL)
    # ------------------------------------------------------------------------

    def __init__(self, lines):
        return super(NgmgShmHpilistParserLogDatum, self).__init__(lines)

    def get_dict_representations(self):
        if self._dict_representations is not None:
            return self._dict_representations

        rv = []
        current_block = []
        old_current_block = []
        is_in_block = False
        for i, line in enumerate(self.lines):
            logger.debug("i: %s, line: %s" % (i, line))
            # ----------------------------------------------------------------
            #   Judging by whether there's a datetime in the line adjust
            #   our behaviour.
            #   -   is_in_block: are we currently processing a block?
            # ----------------------------------------------------------------
            m = self.RE_BLOCK_START.search(line)
            logger.debug("before. m: %s, is_in_block: %s, current_block: %s, old_current_block: %s" % (m, is_in_block, pprint.pformat(current_block), pprint.pformat(old_current_block)))
            if not m and not is_in_block:
                logger.debug("no datetime, not in block, so skip")
                continue
            if not m and is_in_block:
                logger.debug("no datetime, but in a block. append line to current_block and continue")
                current_block.append(line)
                continue
            if m and not is_in_block:
                logger.debug("datetime, but not in a block. odd! start new current_block")
                is_in_block = True
                current_block = [line]
                continue
            elif m and is_in_block:
                logger.debug("datetime, and in a block. current_block is finished.")
                old_current_block = current_block[:]
                current_block = [line]
            logger.debug("after. m: %s, is_in_block: %s, current_block: %s, old_current_block: %s" % (m, is_in_block, pprint.pformat(current_block), pprint.pformat(old_current_block)))
            # ----------------------------------------------------------------

            # ----------------------------------------------------------------
            #   If current_block_is_finished we need to parse the contents
            #   of current_block and append it to rv.
            # ----------------------------------------------------------------
            # The first line must match RE_BLOCK_START
            m = self.RE_BLOCK_START.search(old_current_block[0])
            assert(m)
            hhmmss = m.groupdict()["time"]
            millisecond = m.groupdict()["millisecond"]
            try:
                now = datetime.datetime.utcnow()
                datetime_obj = datetime.datetime.strptime(hhmmss, self.DATETIME_FORMAT)
                datetime_obj = datetime_obj.replace(year = now.year,
                                                    month = now.month,
                                                    day = now.day,
                                                    microsecond = int(millisecond) * 1000)
            except ValueError:
                logger.exception("failed to parse datetime in first line: %s" % (old_current_block[0], ))
                continue
            return_value = {}
            return_value["year"] = str(datetime_obj.year)
            return_value["month"] = str(datetime_obj.month)
            return_value["day"] = str(datetime_obj.day)
            return_value["hour"] = str(datetime_obj.hour)
            return_value["minute"] = str(datetime_obj.minute)
            return_value["second"] = str(datetime_obj.second)
            return_value["millisecond"] = str(datetime_obj.microsecond / 1000)
            return_value["contents"] = '\n'.join(old_current_block)
            return_value["contents_hash"] = base64.b64encode(hashlib.md5(return_value["contents"]).digest())
            return_value["keywords"] = self.tokenize(return_value["contents"])
            # ----------------------------------------------------------------

            # ----------------------------------------------------------------
            #   Go line-by-line and parse for source, event_type, and
            #   component_path.
            # ----------------------------------------------------------------
            for line in old_current_block:
                m = self.RE_SOURCE.search(line)
                if m:
                    return_value["source"] = m.groupdict()["source"]
                    continue
                m = self.RE_EVENT_TYPE.search(line)
                if m:
                    return_value["event_type"] = m.groupdict()["event_type"]
                    continue
                m = self.RE_COMPONENT_PATH.search(line)
                if m:
                    return_value["component_path"] = m.groupdict()["component_path"]
                    continue
            # ----------------------------------------------------------------

            rv.append(return_value)
        self._dict_representations = rv
        self._excess_lines = current_block

        logger.debug("returning: \n%s" % (pprint.pformat(self._dict_representations), ))
        return self._dict_representations

    analyzer = StandardAnalyzer()
    def tokenize(self, input):
        """Given a blob of input prepare a list of strings that is suitable
        for full-text indexing by MongoDB.

        I'm going to cheat and use Whoosh."""

        tokens = []
        for elem in self.analyzer(input):
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
    try:
        fields_to_index = ["datetime", "keywords", "contents_hash", "source", "event_type", "component_path"]
        base_parser.main(APP_NAME, NgmgShmHpilistParserLogDatum, fields_to_index)
    except KeyboardInterrupt:
        logger.debug("CTRL-C")
    finally:
        logger.debug("exiting")

