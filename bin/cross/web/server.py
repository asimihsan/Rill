#!/usr/bin/env python2.7

from gevent import monkey; monkey.patch_all()

import time
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
import base64
import operator

# ----------------------------------------------------------------------------
#   Logging.
# ----------------------------------------------------------------------------
import logging
import logging.handlers
import platform
APP_NAME = "rill_web_server"
if platform.system() == "Windows":
    LOG_FILENAME = r"I:\logs\%s.log" % (APP_NAME, )
    ACCESS_LOG_FILENAME = r"I:\logs\%s_access.log" % (APP_NAME, )
else:
    LOG_FILENAME = r"/var/log/%s.log" % (APP_NAME, )
    ACCESS_LOG_FILENAME = r"/var/log/%s_access.log" % (APP_NAME, )
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

ch2 = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=10*1024*1024, backupCount=10)
ch2.setFormatter(formatter)
logger.addHandler(ch2)

logger = logging.getLogger(APP_NAME)

access_logger = logging.getLogger("%s_access" % (APP_NAME, ))
access_logger.setLevel(logging.DEBUG)
ch3 = logging.handlers.RotatingFileHandler(ACCESS_LOG_FILENAME, maxBytes=10*1024*1024, backupCount=10)
ch3.setFormatter(formatter)
ch3.setLevel(logging.DEBUG)
access_logger.addHandler(ch3)
# ----------------------------------------------------------------------------

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
jinja2_env = jinja2.Environment(loader = jinja2.FileSystemLoader(ROOT_PATH))
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
#   Database connection and queries.
# ----------------------------------------------------------------------------
db = database.Database()
# ----------------------------------------------------------------------------

@bottle.route('/')
def index():
    logger = logging.getLogger("%s.index" % (APP_NAME, ))
    logger.debug("entry.")
    access_logger.debug("index:\n%s" % (pprint.pformat(sorted(bottle.request.items(), key=operator.itemgetter(0))), ))
    data = {}
    template = jinja2_env.get_template('index.html')
    stream = template.stream()
    for chunk in stream:
        yield chunk

@bottle.route('/shm_split_brain')
def shm_split_brain():
    logger = logging.getLogger("%s.shm_split_brain" % (APP_NAME, ))
    logger.debug("entry.")
    access_logger.debug("shm_split_brain:\n%s" % (pprint.pformat(sorted(bottle.request.items(), key=operator.itemgetter(0))), ))

    collections = sorted(db.get_ngmg_shm_messages_collections())
    collection_objects = [db.get_collection(collection) for collection in collections]
    split_brain_log_cursors = [db.get_shm_split_brain_logs(collection, datetime_interval=db.one_day)
                               for collection in collection_objects]
    log_data = zip(collections, split_brain_log_cursors)
    template = jinja2_env.get_template('shm_split_brain.html')
    stream = template.stream(log_data = log_data)
    for chunk in stream:
        yield chunk

@bottle.route('/ep_error_instances')
def ep_error_instances():
    logger = logging.getLogger("%s.ep_error_instances" % (APP_NAME, ))
    logger.debug("entry.")
    access_logger.debug("ep_error_instances:\n%s" % (pprint.pformat(sorted(bottle.request.items(), key=operator.itemgetter(0))), ))

    # ------------------------------------------------------------------------
    #   Validate inputs.
    # ------------------------------------------------------------------------
    error_id = bottle.request.query.error_id
    assert(error_id)
    assert(len(error_id) != 0)
    error_id_decoded = base64.urlsafe_b64decode(str(error_id))
    # ------------------------------------------------------------------------

    collections_and_cursors = db.get_ep_error_instances(error_id = error_id_decoded)
    collections_and_cursors.sort(key=operator.itemgetter(0))
    template = jinja2_env.get_template('ep_error_instances.html')
    stream = template.stream(error_id = error_id_decoded,
                             collections_and_cursors = collections_and_cursors)
    for chunk in stream:
        yield chunk

@bottle.route('/ep_error_count')
def ep_error_count():
    logger = logging.getLogger("%s.ep_error_count" % (APP_NAME, ))
    logger.debug("entry.")
    access_logger.debug("ep_error_count:\n%s" % (pprint.pformat(sorted(bottle.request.items(), key=operator.itemgetter(0))), ))

    template = jinja2_env.get_template('ep_error_count.html')
    stream = template.stream()
    for chunk in stream:
        yield chunk

@bottle.route('/ep_error_count', method='POST')
def ep_error_count():
    logger = logging.getLogger("%s.ep_error_count_post" % (APP_NAME, ))
    logger.debug("entry.")
    access_logger.debug("ep_error_count_post:\n%s" % (pprint.pformat(sorted(bottle.request.items(), key=operator.itemgetter(0))), ))

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
    error_id_to_collection = {}
    summarized_error_data = {}
    summarized_warning_data = {}
    start_datetime = datetime.datetime.utcnow() - datetime_interval_obj
    for (data_obj, key_name) in [(summarized_error_data, "error"),
                                 (summarized_warning_data, "warning")]:
        logger.debug("ep count for type: %s" % (key_name, ))
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
            logger.debug("collection_name: %s" % (collection_name, ))
            collection = db.get_collection(collection_name)
            result = collection.group(key = q_key,
                                      condition = q_condition,
                                      initial = q_initial,
                                      reduce = q_reduce)
            for elem in result:
                key = elem["error_id"]
                value = int(elem["count"])
                data_obj[key] = data_obj.get(key, 0) + value

                # While we're here stash which collection this error_id
                # shows up in so we can come back later and get an example.
                if key not in error_id_to_collection:
                    error_id_to_collection[key] = collection

    sorted_warning_data = summarized_warning_data.items()
    sorted_warning_data.sort(key=operator.itemgetter(1), reverse=True)
    sorted_error_data = summarized_error_data.items()
    sorted_error_data.sort(key=operator.itemgetter(1), reverse=True)
    total_warnings = sum(elem[1] for elem in sorted_warning_data)
    total_errors = sum(elem[1] for elem in sorted_error_data)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Go back and find one example of each error_id, any will do.
    # ------------------------------------------------------------------------
    for sorted_data in (sorted_warning_data, sorted_error_data):
        for (i, datum) in enumerate(sorted_data):
            (error_id, count) = datum
            example = ""
            if error_id in error_id_to_collection:
                collection = error_id_to_collection[error_id]
                example_result = collection.find_one({"error_id": error_id})
                contents = example_result["contents"]
                example = contents.partition("[%s]" % (error_id, ))[-1].strip()
            error_id_instances_link = r'/ep_error_instances?error_id=%s' % (base64.urlsafe_b64encode(error_id), )
            sorted_data[i] = (error_id, count, example, error_id_instances_link)
    # ------------------------------------------------------------------------

    template = jinja2_env.get_template('ep_error_count_results.html')
    stream = template.stream(log_data = [],
                             sorted_warning_data = sorted_warning_data,
                             total_warnings = total_warnings,
                             sorted_error_data = sorted_error_data,
                             total_errors = total_errors,
                             datetime_interval = datetime_interval)
    for chunk in stream:
        yield chunk

@bottle.route('/full_text_search')
def full_text_search():
    logger = logging.getLogger("%s.full_text_search" % (APP_NAME, ))
    logger.debug("entry.")
    access_logger.debug("full_text_search:\n%s" % (pprint.pformat(sorted(bottle.request.items(), key=operator.itemgetter(0))), ))
    template = jinja2_env.get_template('full_text_search.html')
    stream = template.stream()
    for chunk in stream:
        yield chunk

@bottle.route('/full_text_search', method='POST')
def full_text_search_results():
    logger = logging.getLogger("%s.full_text_search_results" % (APP_NAME, ))
    logger.debug("entry.")
    access_logger.debug("full_text_search_results:\n%s" % (pprint.pformat(sorted(bottle.request.items(), key=operator.itemgetter(0))), ))
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
    logger.debug("search_string: %s, log_type: %s, datetime_interval: %s, tokens: %s" % (search_string, log_type, datetime_interval, tokens))
    # ------------------------------------------------------------------------

    datetime_interval_obj = getattr(db, datetime_interval)
    collection_names = sorted(db.get_collection_names(name_filter = log_type))
    log_data = []
    for collection_name in collection_names:
        collection = db.get_collection(collection_name)
        cursor = db.get_full_text_search_of_logs(collection = collection,
                                                 search_argument = tokens,
                                                 datetime_interval = datetime_interval_obj)
        log_data.append((collection_name, cursor))

    template = jinja2_env.get_template('full_text_search_results.html')
    stream = template.stream(log_data = log_data)
    for chunk in stream:
        yield chunk

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

bottle.debug(True)
bottle.run(host="0.0.0.0",
           port=8080,
           reloader=True,
           interval=0.5,
           server='gevent')

