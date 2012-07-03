#!/usr/bin/env python2.7

# ----------------------------------------------------------------------------
#   Age the MongoDB collections. Removing a document is a database-level
#   blocking operation, and is very expensive. Hence do not execute a single
#   query to delete all matching documents. We delete in blocks of documents.
#
#   See:
#     http://groups.google.com/group/mongodb-user/browse_thread/thread/5d5dd12e37382b5b?pli=1
# ----------------------------------------------------------------------------

import os
import sys
import database
import datetime
import pdb
import time
import multiprocessing
import random
import psutil
import pymongo

# ----------------------------------------------------------------------------
#   Constants.
# ----------------------------------------------------------------------------
one_day = datetime.timedelta(days=1)
four_days = datetime.timedelta(days=4)
five_days = datetime.timedelta(days=5)
one_week = datetime.timedelta(days=7)
ten_days = datetime.timedelta(days=10)
two_weeks = datetime.timedelta(days=14)
one_minute = datetime.timedelta(minutes=1)
remove_block_size = 150
maximum_time_per_collection = 10 * 60 # 10 minutes
LOG_FILENAME = r"/var/log/rill/age_database.log"
INTERVAL_SIZE = four_days
# ----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
#   Logging.
# -----------------------------------------------------------------------------
APP_NAME = "age_database"
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

def main():
    """ Delete old database logs.

    Removing documents blocks readers so only delete documents in chunks.
    Moreover, we guarantee we're going to delete documents from oldest
    to newest because this operation may take a very long time and we
    don't want the user experience of reading to be too odd.
    """
    logger = logging.getLogger("%s.main" % (APP_NAME, ))
    logger.debug("entry.")

    database_names = ["logs", "pings", "mv_trees"]
    for database_name in database_names:
        logger.debug("database_name: %s" % (database_name, ))
        top_db = database.Database(database_name = database_name, logger = logger)
        write_database = top_db.write_database
        collection_names = write_database.collection_names()
        random.shuffle(collection_names)
        if "system.indexes" in collection_names:
            collection_names.remove("system.indexes")
        if database_name == "mv_trees":
            datetime_query_string = "query_datetime"
        else:
            datetime_query_string = "datetime"
        for collection_name in collection_names:
            logger.debug("collection_name: %s" % (collection_name, ))
            logger = logging.getLogger("%s.main.%s" % (APP_NAME, collection_name, ))
            start_time = time.time()
            oldest_date = datetime.datetime.utcnow() - INTERVAL_SIZE
            newest_date = datetime.datetime.utcnow() + one_day

            collection = write_database[collection_name]
            cursor = collection.find({"$or": [{datetime_query_string: {'$lt': oldest_date}},
                                              {datetime_query_string: {'$gt': newest_date}}]},
                                     {'_id': 1}).sort(datetime_query_string, 1) #.limit(remove_block_size)
            logger.debug("total number of documents: %s. documents to delete remaining: %s" % (collection.count(), cursor.count()))
            count = cursor.count(with_limit_and_skip = True)
            collection_cnt = 0
            while (time.time() - start_time) <= maximum_time_per_collection:
                logger.debug("collection_cnt: %s" % collection_cnt)
                is_collection_finished = False
                ids = []
                try:
                    cnt = 0
                    while cnt < remove_block_size:
                        ids.append(cursor.next()['_id'])
                        cnt += 1
                except StopIteration:
                    logger.debug("no more rows left.")
                    is_collection_finished = True
                remove_rc = collection.remove({'_id': {'$in': ids}},
                                              safe = True,
                                              w = "majority")
                logger.debug("remove_rc: %s" % (remove_rc, ))
                if is_collection_finished:
                    logger.debug("collection is finished.")
                    break
                collection_cnt += 1

if __name__ == "__main__":
    try:
        p = multiprocessing.Process(target = main)
        time_start = time.time()
        p.daemon = True
        p.start()
        psutil.Process(p.pid).nice = 19
        timeout = 60 * 60 # 60 minutes
        while p.is_alive() and ((time.time() - time_start) <= timeout):
            time.sleep(1)
        if p.is_alive():
            logger.error("command is still running, taking too long.")
        p.terminate()
    except:
        logger.exception("Unhandled exception.")

