#!/usr/bin/env python2.7

# ----------------------------------------------------------------------------
#   Dump the log contents between two datetimes into a temporary file,
#   then open it in vim.
#
#   Hint: don't load the whole thing into memory! :).
# ----------------------------------------------------------------------------

import os
import sys
import database
import datetime
import pdb
import time
import argparse
import pprint
import tempfile
from functools import total_ordering

# ----------------------------------------------------------------------------
#   Constants.
# ----------------------------------------------------------------------------
four_hours = datetime.timedelta(hours=4)
six_hours = datetime.timedelta(hours=6)
eight_hours = datetime.timedelta(hours=8)
ten_hours = datetime.timedelta(hours=10)
twelve_hours = datetime.timedelta(hours=12)
one_day = datetime.timedelta(days=1)
five_days = datetime.timedelta(days=5)
one_week = datetime.timedelta(days=7)
ten_days = datetime.timedelta(days=10)
two_weeks = datetime.timedelta(days=14)
one_minute = datetime.timedelta(minutes=1)
LOG_FILENAME = r"/var/log/dump_log_contents.log"
INTERVAL = ten_hours
# ----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
#   Logging.
# -----------------------------------------------------------------------------
APP_NAME = "dump_log_contents"
import logging
import logging.handlers
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=10*1024*1024, backupCount=10)
fh.setFormatter(formatter)
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)
# -----------------------------------------------------------------------------


def parse_args():
    parser = argparse.ArgumentParser("Dump logs and view them in vim.")
    parser.add_argument("--start",
                        dest="start_datetime",
                        metavar="DATETIME",
                        default=None,
                        help="Start datetime")
    parser.add_argument("--end",
                        dest="end_datetime",
                        metavar="DATETIME",
                        default=None,
                        help="End datetime.")
    parser.add_argument("--collection_name",
                        dest="collection_name",
                        metavar="STRING",
                        default=None,
                        help="Collection name.")
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
    return (args, parser)

def main():
    logger = logging.getLogger("%s.main" % (APP_NAME, ))
    logger.debug("entry.")

    # ------------------------------------------------------------------------
    #   Open up the logs database, get a list of collections.
    # ------------------------------------------------------------------------
    database_name = "logs"
    top_db = database.Database(database_name = database_name)
    read_database = top_db.read_database
    collection_names = [str(elem) for elem in sorted(read_database.collection_names())]
    if "system.indexes" in collection_names:
        collection_names.remove("system.indexes")
    datetime_query_string = "datetime"
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Gether and validate inputs.
    # ------------------------------------------------------------------------
    (args, parser) = parse_args()
    if args.collection_name is None:
        logger.info("collection_name required. Choose from:\n%s" % (pprint.pformat(collection_names), ))
        parser.print_help()
        sys.exit(1)
    #if args.collection_name not in collection_names:
    #    logger.error("collection_name '%s' not valid. Choose from:\n%s" % (args.collection_name, pprint.pformat(collection_names), ))
    #    parser.print_help()
    #    sys.exit(1)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Get logs.
    # ------------------------------------------------------------------------
    oldest_date = datetime.datetime.utcnow() - INTERVAL
    newest_date = datetime.datetime.utcnow()
    collections = [read_database[collection_name] for collection_name in collection_names if args.collection_name in collection_name]
    for collection in collections:
        collection.ensure_index([(datetime_query_string, -1)],
                                background = True)
    query_part = {datetime_query_string: {'$gt': oldest_date,
                                          '$lt': newest_date}}
    filter_part = {'contents': 1, 'datetime': 1}
    cursors = []
    for collection in collections:
        logger.debug("collection: %s" % (collection, ))
        cursor = collection.find(query_part, filter_part)
        cursor.batch_size(100000)
        cursor_sorted = cursor.sort(datetime_query_string, 1)
        count = cursor_sorted.count(with_limit_and_skip = True)
        logger.debug("There are %s logs in the datetime range." % (cursor_sorted.count(), ))
        cursors.append(cursor)
    # ------------------------------------------------------------------------

    @total_ordering
    class Log(object):
        def __init__(self, cursor):
            self._cursor = cursor
            self._cnt = 0
            self._count = self.cursor.count(with_limit_and_skip = True)
            self._current_contents = self._cursor[self._cnt]["contents"]
            self._current_datetime = self._cursor[self._cnt]["datetime"]

        @property
        def cursor(self):
            return self._cursor

        @property
        def cnt(self):
            return self._cnt

        @cnt.setter
        def cnt(self, value):
            self._cnt = value
            self._current_contents = self._cursor[self._cnt]["contents"]
            self._current_datetime = self._cursor[self._cnt]["datetime"]

        @property
        def count(self):
            return self._count

        @property
        def current_contents(self):
            return self._current_contents

        @property
        def current_datetime(self):
            return self._current_datetime


        def is_finished(self):
            return self._cnt >= (self._count - 1)

        def __lt__(self, other):
            return self._current_datetime < other.current_datetime

        def __eq__(self, other):
            return self._current_datetime == other.current_datetime

        def consume(self):
            rv = self._current_contents
            self.cnt = self.cnt + 1
            return rv

    logs = [Log(cursor) for cursor in cursors]

    # ------------------------------------------------------------------------
    #   Dump logs to file and open in vim.
    # ------------------------------------------------------------------------
    tempfile.tempdir = r"/var"
    new_file = tempfile.NamedTemporaryFile(delete=False)
    new_file.close()
    new_file_path = new_file.name
    try:
        logger.debug("Writing results to file '%s'..." % (new_file_path, ))
        with open(new_file_path, "w", buffering=4096) as f:
            while len(logs) > 0:
                current_log = min(logs)
                value = current_log.consume()
                f.write(value + "\n")
                if current_log.is_finished():
                    logs.remove(current_log)
        logger.debug("Opening %s in vim" % (new_file_path, ))
        os.system("vim %s" % (new_file_path, ))
    finally:
        logger.debug("Deleting %s" % (new_file_path, ))
        os.remove(new_file_path)
    # ------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main()
    except:
        logger.exception("Unhandled exception.")

