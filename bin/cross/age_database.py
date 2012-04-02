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

# ----------------------------------------------------------------------------
#   Constants.
# ----------------------------------------------------------------------------
one_day = datetime.timedelta(days=1)
five_days = datetime.timedelta(days=5)
one_week = datetime.timedelta(days=7)
two_weeks = datetime.timedelta(days=14)
one_minute = datetime.timedelta(minutes=1)
remove_block_size = 150
LOG_FILENAME = r"/var/log/age_database.log"
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
    oldest_date = datetime.datetime.utcnow() - five_days
    newest_date = datetime.datetime.utcnow() + one_day

    for database_name in database_names:
        logger.debug("database_name: %s" % (database_name, ))
        top_db = database.Database(database_name = database_name)
        write_database = top_db.write_database
        collection_names = sorted(write_database.collection_names())
        if "system.indexes" in collection_names:
            collection_names.remove("system.indexes")
        if database_name == "mv_trees":
            datetime_query_string = "query_datetime"
        else:
            datetime_query_string = "datetime"
        for collection_name in collection_names:
            logger.debug("collection_name: %s" % (collection_name, ))
            while True:
                collection = write_database[collection_name]
                cursor = collection.find({"$or": [{datetime_query_string: {'$lt': oldest_date}},
                                                  {datetime_query_string: {'$gt': newest_date}}]},
                                         {'_id': 1}).sort(datetime_query_string, 1).limit(remove_block_size)
                logger.debug("collection: %s. total number of documents: %s. documents to delete remaining: %s" % (collection_name, collection.count(), cursor.count()))
                count = cursor.count(with_limit_and_skip = True)
                if count == 0:
                    logger.debug("finished with current collection.")
                    break
                ids = [elem['_id'] for elem in cursor]
                remove_rc = collection.remove({'_id': {'$in': ids}}, safe = True)
                logger.debug("remove_rc: %s" % (remove_rc, ))

if __name__ == "__main__":
    try:
        main()
    except:
        logger.exception("Unhandled exception.")

