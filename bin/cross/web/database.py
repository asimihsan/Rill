import os
import sys
cross_root = os.path.abspath(os.path.join(__file__, os.pardir))
sys.path.append(cross_root)
from utilities import retry

import datetime
import pymongo
import re

import time
import functools

# -----------------------------------------------------------------------------
#   Database constants.
# -----------------------------------------------------------------------------
servers = ["magpie:27017", "mink:27017", "rabbit:27107", "rat:27107", "fox:27017"]
# -----------------------------------------------------------------------------

import logging
logger = logging.getLogger("rill_web_server.database")

class Database(object):
    one_year = datetime.timedelta(days=365)
    one_week = datetime.timedelta(days=7)
    one_day = datetime.timedelta(days=1)
    one_month = datetime.timedelta(days=31)
    three_days = datetime.timedelta(days=3)
    six_hours = datetime.timedelta(hours=6)
    one_hour = datetime.timedelta(hours=1)
    fifteen_minutes = datetime.timedelta(minutes=15)
    five_minutes = datetime.timedelta(minutes=5)
    ten_minutes = datetime.timedelta(minutes=10)

    ngmg_shm_messages_collection_filter = "ngmg_shm_messages"
    ngmg_messages_collection_filter = "ngmg_messages"
    ngmg_ep_collection_filter = "ngmg_ep"
    ngmg_ms_messages_collection_filter = "ngmg_ms_messages"

    def __init__(self, database_name=None):
        if not database_name:
            database_name = "logs"
        self.connection = pymongo.ReplicaSetConnection(",".join(servers), replicaSet='rill')
        self.connection.read_preference = pymongo.ReadPreference.SECONDARY
        self.database = self.connection[database_name]

    @retry()
    def get_collection(self, collection_name):
        rv = self.database[collection_name]
        return rv

    @retry()
    def get_collection_names(self, name_filter=None):
        all_collection_names = self.database.collection_names()
        if name_filter:
            collection_names = [elem for elem in all_collection_names if re.search(name_filter, elem)]
        else:
            collection_names = all_collection_names
        return collection_names

    @retry()
    def get_ngmg_shm_messages_collections(self):
        return self.get_collection_names(name_filter = self.ngmg_shm_messages_collection_filter)

    @retry()
    def get_ngmg_ep_collections(self):
        collection_names = self.get_collection_names(name_filter = self.ngmg_ep_collection_filter)
        collections = [self.get_collection(name) for name in collection_names]
        return collections

    @retry()
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
                datetime_interval = self.one_week
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

    @retry()
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

    @retry()
    def get_full_text_search_of_logs(self,
                                     collection,
                                     include_search_argument,
                                     exclude_search_argument = None,
                                     datetime_interval = None,
                                     fields_to_return = ["contents"],
                                     fields_to_ignore = ["_id"],
                                     query_argument = None):
        #if query_argument:
            #sub_queries = "{'keywords': {'$all': %s}}" % (elem, ) for elem in
            #query_part = {'keywords': {'$and':
        search_part = {'$all': include_search_argument}
        if exclude_search_argument:
            search_part['$nin'] = exclude_search_argument
        query_part = {'keywords': search_part}
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

        logger.debug("collection: %s" % (collection, ))
        logger.debug("query_part: %s" % (query_part, ))
        logger.debug("filter_part: %s" % (filter_part, ))
        logger.debug("number of results: %s" % (results_cursor.count(), ))

        return results_cursor

    @retry()
    def get_shm_split_brain_logs(self,
                                 collection,
                                 datetime_interval=None,
                                 fields_to_return = ["contents"],
                                 fields_to_ignore = ["_id"]):
        include_search_argument = ['brain']
        return self.get_full_text_search_of_logs(collection,
                                                 include_search_argument,
                                                 datetime_interval,
                                                 fields_to_return,
                                                 fields_to_ignore)

    @retry()
    def get_shm_memory_data(self,
                            collection,
                            datetime_interval = None):
        # Mar 3 15:11:36 emer_mf106-wrlinux daemon.alert SYSSTAT(memMonitor)[15381]: Memory check OK; free memory: 143676 kB (56%)
        include_search_argument = ['memmonitor', 'free', 'memory']
        if not datetime_interval:
            datetime_interval = self.one_week
        full_text_cursor = self.get_full_text_search_of_logs(collection = collection,
                                                             include_search_argument = include_search_argument,
                                                             datetime_interval = datetime_interval,
                                                             fields_to_return = ['contents'],
                                                             fields_to_ignore = ['_id'])
        results = []
        datetime_format = "%Y %b %d %H:%M:%S"
        re_expr = "(?P<month>\S+)\s+(?P<day>\d+)\s+(?P<time>\d+:\d+:\d+).*\((?P<percent_free>\d+)%\)"
        re_obj = re.compile(re_expr)
        for row in full_text_cursor:
            contents = row["contents"]
            m = re_obj.search(contents)
            if not m:
                continue
            in_year = str(datetime.datetime.utcnow().year)
            in_month = m.groupdict()["month"]
            in_day = m.groupdict()["day"]
            in_time = m.groupdict()["time"]
            full_datetime = " ".join([in_year, in_month, in_day, in_time])
            try:
                datetime_obj = datetime.datetime.strptime(full_datetime, datetime_format)
            except ValueError:
                continue

            datetime_epoch_milli = int(time.mktime(datetime_obj.timetuple())) * 1000
            percent_free = int(m.groupdict()["percent_free"])
            results.append((datetime_epoch_milli, percent_free))
        return results

    @retry()
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

