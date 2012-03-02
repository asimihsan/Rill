#!/usr/bin/env python2.7

import os
import sys
import bottle
import jinja2
import pymongo
import database
import pprint
from whoosh.analysis import StandardAnalyzer
import operator
import bson
import datetime

# ----------------------------------------------------------------------------
#   Constants.
# ----------------------------------------------------------------------------
ROOT_PATH = os.path.abspath(os.path.join(__file__, os.pardir))
CSS_PATH = os.path.join(ROOT_PATH, "css")
JS_PATH = os.path.join(ROOT_PATH, "js")
IMG_PATH = os.path.join(ROOT_PATH, "img")
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
#   Templates.
# ----------------------------------------------------------------------------
import jinja2
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
#   Database connection and queries.
# ----------------------------------------------------------------------------
db = database.Database()
# ----------------------------------------------------------------------------

@bottle.route('/')
def index():
    data = {}
    return bottle.jinja2_template("index.html", data=data)

@bottle.route('/shm_split_brain')
def shm_split_brain():
    collections = sorted(db.get_ngmg_shm_messages_collections())
    collection_objects = [db.get_collection(collection) for collection in collections]
    split_brain_log_cursors = [db.get_shm_split_brain_logs(collection, datetime_interval=db.one_day)
                               for collection in collection_objects]
    log_data = []
    for (collection, split_brain_log_cursor) in zip(collections, split_brain_log_cursors):
        results = [elem for elem in split_brain_log_cursor]
        log_data.append((collection, results))
    return bottle.jinja2_template("shm_split_brain.html",
                                  log_data=log_data)

@bottle.route('/ep_error_count')
def ep_error_count():
    return bottle.jinja2_template("ep_error_count.html")

@bottle.route('/ep_error_count', method='POST')
def ep_error_count():
    # ------------------------------------------------------------------------
    #   Validate inputs.
    # ------------------------------------------------------------------------
    valid_intervals = set(["one_hour", "six_hours", "one_day", "one_week"])
    datetime_interval = bottle.request.forms.get("datetime_interval")
    assert(datetime_interval in valid_intervals)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Get raw results.
    #   !!AI in time use map reduce. For now bang it out.
    # ------------------------------------------------------------------------
    datetime_interval_obj = getattr(db, datetime_interval)
    log_type = "ngmg_ep"
    collection_names = sorted(db.get_collection_names(name_filter = log_type))
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Using group() get a count of each error_id.
    # ------------------------------------------------------------------------
    summarized_error_data = {}
    summarized_warning_data = {}
    start_datetime = datetime.datetime.utcnow() - datetime_interval_obj
    for (data_obj, key_name) in [(summarized_error_data, "error"),
                                 (summarized_warning_data, "warning")]:
        print "ep count for type: %s" % (key_name, )
        q_key = {"error_id": True}
        q_condition = {"error_level": {"$in": [key_name]},
                       "error_id": {"$exists": True},
                       "datetime": {"$gt": start_datetime}}
        q_initial = {"count": 0}
        q_reduce = bson.Code("""function(document, aggregator)
                                {
                                    aggregator.count += 1;
                                }""")
        for collection_name in collection_names:
            print "collection_name: %s" % (collection_name, )
            collection = db.get_collection(collection_name)
            result = collection.group(key = q_key,
                                      condition = q_condition,
                                      initial = q_initial,
                                      reduce = q_reduce)
            for elem in result:
                key = elem["error_id"]
                value = int(elem["count"])
                data_obj[key] = data_obj.get(key, 0) + value

    sorted_warning_data = summarized_warning_data.items()
    sorted_warning_data.sort(key=operator.itemgetter(1), reverse=True)
    sorted_error_data = summarized_error_data.items()
    sorted_error_data.sort(key=operator.itemgetter(1), reverse=True)
    total_warnings = sum(elem[1] for elem in sorted_warning_data)
    total_errors = sum(elem[1] for elem in sorted_error_data)
    # ------------------------------------------------------------------------

    return bottle.jinja2_template("ep_error_count_results.html",
                                  log_data = [],
                                  sorted_warning_data = sorted_warning_data,
                                  total_warnings = total_warnings,
                                  sorted_error_data = sorted_error_data,
                                  total_errors = total_errors,
                                  datetime_interval = datetime_interval)

@bottle.route('/full_text_search')
def full_text_search():
    data = {}
    return bottle.jinja2_template("full_text_search.html", data=data)

@bottle.route('/full_text_search', method='POST')
def full_text_search_results():
    # ------------------------------------------------------------------------
    #   Validate inputs.
    # ------------------------------------------------------------------------
    valid_types = set(["ngmg_shm_messages", "ngmg_ep", "ngmg_messages"])
    valid_intervals = set(["one_hour", "six_hours", "one_day", "one_week"])

    search_string = bottle.request.forms.get("search_string")
    log_type = bottle.request.forms.get("log_type")
    datetime_interval = bottle.request.forms.get("datetime_interval")

    assert(log_type in valid_types)
    assert(datetime_interval in valid_intervals)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Tokenize the search string.
    # ------------------------------------------------------------------------
    analyzer = StandardAnalyzer()
    tokens = []
    for elem in analyzer(unicode(search_string)):
        tokens.append(elem.text)
    tokens = list(set(tokens))
    print "search_string: %s, log_type: %s, datetime_interval: %s, tokens: %s" % (search_string, log_type, datetime_interval, tokens)
    # ------------------------------------------------------------------------

    datetime_interval_obj = getattr(db, datetime_interval)
    collection_names = sorted(db.get_collection_names(name_filter = log_type))
    log_data = []
    for collection_name in collection_names:
        collection = db.get_collection(collection_name)
        cursor = db.get_full_text_search_of_logs(collection = collection,
                                                 search_argument = tokens,
                                                 datetime_interval = datetime_interval_obj)
        results = [elem for elem in cursor]
        log_data.append((collection_name, results))
    return bottle.jinja2_template("full_text_search_results.html",
                                  log_data = log_data)
# ----------------------------------------------------------------------------
#   Static files.
# ----------------------------------------------------------------------------
@bottle.route('/favicon.ico')
def server_static():
    return bottle.static_file('favicon.ico', root=ROOT_PATH)

@bottle.route('/css/<filename>')
def server_css_static(filename):
    return bottle.static_file(filename, root=CSS_PATH)

@bottle.route('/img/<filename>')
def server_css_static(filename):
    return bottle.static_file(filename, root=IMG_PATH)

@bottle.route('/js/<filepath:path>')
def server_js_static(filepath):
    return bottle.static_file(filepath, root=JS_PATH)
# ----------------------------------------------------------------------------

#bottle.run(server='tornado')

bottle.debug(True)
bottle.run(host="0.0.0.0",
           port=8080,
           reloader=True,
           interval=0.5)

