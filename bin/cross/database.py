import datetime
import pymongo

import time
import functools

# -----------------------------------------------------------------------------
#   Database constants.
# -----------------------------------------------------------------------------
master_hostname = "magpie"
slave_hostnames = ["magpie", "mink", "rabbit", "rat"]
# -----------------------------------------------------------------------------

class Database(object):
    one_year = datetime.timedelta(days=365)
    one_week = datetime.timedelta(days=7)
    one_day = datetime.timedelta(days=1)
    six_hours = datetime.timedelta(hours=6)
    one_hour = datetime.timedelta(hours=1)
    fifteen_minutes = datetime.timedelta(minutes=15)
    five_minutes = datetime.timedelta(minutes=5)
    ten_minutes = datetime.timedelta(minutes=10)

    def __init__(self, database_name=None):
        if not database_name:
            database_name = "logs"
        self.write_connection = pymongo.Connection(master_hostname)
        self.write_database = self.write_connection[database_name]

        self.read_connection = pymongo.Connection(slave_hostnames)
        self.read_database = self.read_connection[database_name]

    def get_collection(self, collection_name):
        return self.write_database[collection_name]

    def get_read_collection(self, collection_name):
        return self.read_database[collection_name]

    def create_index(self, collection_name, field, index_type=pymongo.DESCENDING):
        return self.ensure_index(collection_name, field, index_type)

    def ensure_index(self, collection_name, field, index_type=pymongo.DESCENDING):
        collection = self.write_database[collection_name]
        if not index_type:
            index = field
        else:
            index = [(field, index_type)]
        return collection.ensure_index(index)

    def get_all_items_from_collection_newer_than(self,
                                                 collection_name,
                                                 datetime_interval,
                                                 fields_to_return = ["query_datetime", "tree"],
                                                 fields_to_ignore = ["_id"]):
        now = datetime.datetime.utcnow()
        collection = self.get_read_collection(collection_name)
        query_part = {"query_datetime": {"$gt": now - datetime_interval}}
        if fields_to_return:
            filter_part = dict([(field, 1) for field in fields_to_return])
        if fields_to_ignore:
            sub_filter = dict([(field, 0) for field in fields_to_ignore])
            filter_part.update(sub_filter)
        results_cursor = collection.find(query_part, filter_part)
        return results_cursor

