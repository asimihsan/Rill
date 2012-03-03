
import datetime
import pymongo
import pymongo.master_slave_connection

import time
import functools

# -----------------------------------------------------------------------------
#   Database constants.
# -----------------------------------------------------------------------------
master = "magpie"
slaves = ["mink", "rabbit", "rat"]
hostnames = [master] + slaves
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

    ngmg_shm_messages_collection_filter = "ngmg_shm_messages"
    ngmg_messages_collection_filter = "ngmg_messages"
    ngmg_ep_collection_filter = "ngmg_ep"

    def __init__(self, database_name=None):
        if not database_name:
            database_name = "logs"
        self.master_connection = pymongo.Connection(master)
        self.slave_connections = [pymongo.Connection(hostname) for hostname in slaves]
        for connection in self.slave_connections:
            connection.read_preference = pymongo.ReadPreference.SECONDARY
        self.connection = pymongo.master_slave_connection.MasterSlaveConnection(self.master_connection,
                                                                                self.slave_connections)
        #self.connection = pymongo.Connection(hostnames)
        self.database = self.connection[database_name]

    def get_collection(self, collection_name):
        return self.database[collection_name]

    def get_collection_names(self, name_filter=None):
        all_collection_names = self.database.collection_names()
        if name_filter:
            collection_names = [elem for elem in all_collection_names if name_filter in elem]
        else:
            collection_names = all_collection_names
        return collection_names

    def get_ngmg_shm_messages_collections(self):
        return self.get_collection_names(name_filter = self.ngmg_shm_messages_collection_filter)

    def get_ngmg_ep_collections(self):
        collection_names = self.get_collection_names(name_filter = self.ngmg_ep_collection_filter)
        collections = [self.get_collection(name) for name in collection_names]
        return collections

    def get_ep_error_instances(self,
                               error_id,
                               datetime_interval = None,
                               fields_to_return = ['contents'],
                               fields_to_ignore = ['_id']):
        collections = self.get_ngmg_ep_collections()
        results = []
        for collection in collections:
            query_part = {'error_id': error_id}
            if not datetime_interval:
                datetime_interval = self.one_day
            start_datetime = datetime.datetime.utcnow() - datetime_interval
            query_part["datetime"] = {"$gt": start_datetime}
            if fields_to_return:
                filter_part = dict([(field, 1) for field in fields_to_return])
            if fields_to_ignore:
                sub_filter = dict([(field, 0) for field in fields_to_ignore])
                filter_part.update(sub_filter)
            results_cursor = collection.find(query_part, filter_part)
            results_cursor_sorted = results_cursor.sort("datetime", -1)
            results.append((collection, results_cursor_sorted))
        return results

    def get_ep_warnings_and_errors(self,
                                   collection,
                                   datetime_interval = None,
                                   fields_to_return = ['contents', 'error_level', 'error_id'],
                                   fields_to_ignore = ['_id']):
        search_argument = ['error', 'warning']
        query_part = {'error_level': {'$in': search_argument}}
        if not datetime_interval:
            datetime_interval = self.one_day
        start_datetime = datetime.datetime.utcnow() - datetime_interval
        query_part["datetime"] = {"$gt": start_datetime}
        query_part["error_id"] = {"$exists": True}
        if fields_to_return:
            filter_part = dict([(field, 1) for field in fields_to_return])
        if fields_to_ignore:
            sub_filter = dict([(field, 0) for field in fields_to_ignore])
            filter_part.update(sub_filter)
        results_cursor = collection.find(query_part, filter_part)
        results_cursor_sorted = results_cursor.sort("datetime", -1)
        return results_cursor

    def get_full_text_search_of_logs(self,
                                     collection,
                                     search_argument,
                                     datetime_interval = None,
                                     fields_to_return = ["contents"],
                                     fields_to_ignore = ["_id"]):
        query_part = {'keywords': {'$all': search_argument}}
        if not datetime_interval:
            datetime_interval = self.one_day
        start_datetime = datetime.datetime.utcnow() - datetime_interval
        query_part["datetime"] = {"$gt": start_datetime}
        if fields_to_return:
            filter_part = dict([(field, 1) for field in fields_to_return])
        if fields_to_ignore:
            sub_filter = dict([(field, 0) for field in fields_to_ignore])
            filter_part.update(sub_filter)
        results_cursor = collection.find(query_part, filter_part)
        results_cursor_sorted = results_cursor.sort("datetime", -1)
        return results_cursor

    def get_shm_split_brain_logs(self,
                                 collection,
                                 datetime_interval=None,
                                 fields_to_return = ["contents"],
                                 fields_to_ignore = ["_id"]):
        search_argument = ['brain']
        return self.get_full_text_search_of_logs(collection,
                                                 search_argument,
                                                 datetime_interval,
                                                 fields_to_return,
                                                 fields_to_ignore)

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
