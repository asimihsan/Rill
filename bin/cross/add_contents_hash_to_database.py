#!/usr/bin/env python2.7

# ----------------------------------------------------------------------------
#  One-off script to help add contents_hash fields to all logs
# ----------------------------------------------------------------------------

import os
import sys
import database
import datetime
import pdb
import base64
import hashlib

# ----------------------------------------------------------------------------
#   Constants.
# ----------------------------------------------------------------------------
one_week = datetime.timedelta(days=7)
two_weeks = datetime.timedelta(days=14)
one_minute = datetime.timedelta(minutes=1)
LOG_FILENAME = r"/var/log/add_contents_hash_to_database.log"
# ----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
#   Logging.
# -----------------------------------------------------------------------------
APP_NAME = "add_contents_hash_to_database"
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
    """ Add contents hashes to logs database.
    """
    logger = logging.getLogger("%s.main" % (APP_NAME, ))
    logger.debug("entry.")

    top_db = database.Database(database_name = "logs")
    write_database = top_db.write_database
    collection_names = write_database.collection_names()
    if "system.indexes" in collection_names:
        collection_names.remove("system.indexes")
    datetime_query_string = "datetime"
    cnt = 0
    for collection_name in collection_names:
        logger.debug("collection_name: %s" % (collection_name, ))
        collection = write_database[collection_name]
        cursor = collection.find({"contents": {"$exists": True}, "contents_hash": {"$exists": False}})
        logger.debug("number of rows to update: %s" % (cursor.count(), ))
        for row in cursor:
            contents = row["contents"]
            contents_hash = base64.b64encode(hashlib.md5(contents).digest())
            collection.update(row, {"$set": {"contents_hash": contents_hash}})
            cnt += 1
            if cnt % 10000 == 0:
                logger.debug("cnt: %s" % (cnt, ))

if __name__ == "__main__":
    main()
