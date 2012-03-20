#!/usr/bin/env python2.7

import gevent
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
from whoosh.qparser import QueryParser
import whoosh.query

import operator
import bson
import datetime
import base64
import operator
import urllib
from string import Template

#from real_time_stream import real_time_stream

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

@bottle.route('/shm_memory_charts')
def shm_memory_charts():
    logger = logging.getLogger("%s.shm_memory_charts" % (APP_NAME, ))
    logger.debug("entry.")
    access_logger.debug("shm_memory_charts:\n%s" % (pprint.pformat(sorted(bottle.request.items(), key=operator.itemgetter(0))), ))

    collections = sorted(db.get_ngmg_shm_messages_collections())
    friendly_collection_names = [elem.partition(db.ngmg_shm_messages_collection_filter)[0].strip("_").replace(".", "_")
                                 for elem in collections]
    collection_objects = [db.get_collection(collection) for collection in collections]
    jobs = []
    for collection in collection_objects:
        job = gevent.spawn(db.get_shm_memory_data, collection)
        jobs.append(job)
    gevent.joinall(jobs)
    memory_data = []
    for job in jobs:
        memory_datum = job.value
        memory_datum.reverse()
        # var d2 = [[0, 3], [4, 8], [8, 5], [9, 13]];
        elems1 = ["[%s, %s]" % (epoch, percent_free) for (epoch, percent_free) in memory_datum]
        elems2 = ", ".join(elems1)
        memory_datum_js_string = "[%s]" % (elems2, )
        memory_data.append(memory_datum_js_string)
    log_data = zip(collections, friendly_collection_names, memory_data)
    template = jinja2_env.get_template('shm_memory_charts.html')
    stream = template.stream(log_data = log_data)
    for chunk in stream:
        yield chunk

@bottle.route('/shm_error_count')
def shm_error_count():
    logger = logging.getLogger("%s.shm_error_count" % (APP_NAME, ))
    logger.debug("entry.")
    access_logger.debug("shm_error_count:\n%s" % (pprint.pformat(sorted(bottle.request.items(), key=operator.itemgetter(0))), ))

    template = jinja2_env.get_template('shm_error_count.html')
    stream = template.stream()
    for chunk in stream:
        yield chunk

@bottle.route('/shm_error_count', method='POST')
def shm_error_count():
    logger = logging.getLogger("%s.shm_error_count_post" % (APP_NAME, ))
    logger.debug("entry.")
    access_logger.debug("shm_error_count_post:\n%s" % (pprint.pformat(sorted(bottle.request.items(), key=operator.itemgetter(0))), ))

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
    log_type = "ngmg_shm_messages"
    collection_names = sorted(db.get_collection_names(name_filter = log_type))
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   A document in a ms_messages collection, if it relates to a ShM
    #   failure, will include the following key:
    #
    #   "failure_id" : "../../../infra/code/shsysmon/shdamhpi.c:147 - (sahpi_rc == (SaErrorT)0x0000)",
    #
    #   ShMs do not currently have types of error, just asserts.
    # ------------------------------------------------------------------------
    collections = [db.get_collection(collection_name) for collection_name in collection_names]
    start_datetime = datetime.datetime.utcnow() - datetime_interval_obj
    q_key_failure_id = {"failure_id": True}
    q_condition_failure_id = {"failure_id": {"$exists": True},
                              "datetime": {"$gt": start_datetime}}
    q_initial_failure_id = {"count": 0}
    q_reduce_failure_id = bson.Code("""function(document, aggregator)
                                       {
                                          aggregator.count += 1;
                                       }""")
    jobs = []
    for collection in collections:
        job = gevent.spawn(collection.group,
                           key = q_key_failure_id,
                           condition = q_condition_failure_id,
                           initial = q_initial_failure_id,
                           reduce = q_reduce_failure_id)
        jobs.append(job)
    gevent.joinall(jobs)
    failure_id_to_count = {}
    failure_id_to_collection = {}
    for (collection_name, collection, job) in zip(collection_names, collections, jobs):
        for result in job.value:
            count = result["count"]
            failure_id = result["failure_id"]
            failure_id_to_count[failure_id] = failure_id_to_count.get(failure_id, 0) + int(count)
            failure_id_to_collection[failure_id] = collection
    failure_ids_and_counts = sorted(failure_id_to_count.items(), key=operator.itemgetter(1), reverse=True)
    logger.debug("failure_id_and_count: \n%s" % (pprint.pformat(failure_ids_and_counts), ))
    # ------------------------------------------------------------------------

    failure_id_to_full_text_link = {}
    link_template = Template(r"/full_text_search_results?include_search_string=${include_search_string}&datetime_interval=${datetime_interval}&log_type=${log_type}&exclude_search_string=")
    for failure_id in failure_id_to_count:
        link = link_template.substitute(include_search_string = base64.urlsafe_b64encode(failure_id),
                                        datetime_interval = base64.urlsafe_b64encode(datetime_interval),
                                        log_type = base64.urlsafe_b64encode(log_type))
        failure_id_to_full_text_link[failure_id] = link
    template = jinja2_env.get_template('shm_error_count_results.html')
    stream = template.stream(failure_ids_and_counts = failure_ids_and_counts,
                             failure_id_to_full_text_link = failure_id_to_full_text_link,
                             datetime_interval = datetime_interval)
    for chunk in stream:
        yield chunk

@bottle.route('/intel_error_count')
def intel_error_count():
    logger = logging.getLogger("%s.intel_error_count" % (APP_NAME, ))
    logger.debug("entry.")
    access_logger.debug("intel_error_count:\n%s" % (pprint.pformat(sorted(bottle.request.items(), key=operator.itemgetter(0))), ))

    template = jinja2_env.get_template('intel_error_count.html')
    stream = template.stream()
    for chunk in stream:
        yield chunk

@bottle.route('/intel_error_count', method='POST')
def intel_error_count():
    logger = logging.getLogger("%s.intel_error_count_post" % (APP_NAME, ))
    logger.debug("entry.")
    access_logger.debug("intel_error_count_post:\n%s" % (pprint.pformat(sorted(bottle.request.items(), key=operator.itemgetter(0))), ))

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
    log_type = "ngmg_ms_messages"
    collection_names = sorted(db.get_collection_names(name_filter = log_type))
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   A document in a ms_messages collection, if it relates to an Intel
    #   failure, will include the following two keys:
    #
    #   "failure_type" : "Assertion (trigger restart)",
    #   "failure_id" : "'(!tcp_connection_failed)', file ../../../msw/code/dcim/dcimfsmi.c, line 455",
    #
    #   The catch is that, unlike EP error events, where we knew there
    #   were two types of EP error event ('warning' and 'error'), I don't
    #   want to make assumptions about the types of "failure_type" we could
    #   encounter.
    #
    #   Hence, first step is to get a set of unique failure types
    #   _within this time period_. If we agree to not know, a priori, what
    #   Intel error events are possible, we only need to get unique
    #   event types from our time period.
    #
    #   We're going to need two 'group' calls. One to gather 'failure_type'
    #   and one to gather 'failure_id'. Expensive! Let's gevent.spawn
    #   the whole lot and punt it.
    # ------------------------------------------------------------------------
    collections = [db.get_collection(collection_name) for collection_name in collection_names]
    start_datetime = datetime.datetime.utcnow() - datetime_interval_obj
    q_key_failure_id = {"failure_id": True}
    q_condition_failure_id = {"failure_id": {"$exists": True},
                              "datetime": {"$gt": start_datetime}}
    q_initial_failure_id = {"count": 0}
    q_reduce_failure_id = bson.Code("""function(document, aggregator)
                                       {
                                          aggregator.count += 1;
                                       }""")
    jobs = []
    for collection in collections:
        job = gevent.spawn(collection.group,
                           key = q_key_failure_id,
                           condition = q_condition_failure_id,
                           initial = q_initial_failure_id,
                           reduce = q_reduce_failure_id)
        jobs.append(job)
    gevent.joinall(jobs)
    failure_id_to_count = {}
    failure_id_to_collection = {}
    for (collection_name, collection, job) in zip(collection_names, collections, jobs):
        for result in job.value:
            count = result["count"]
            failure_id = result["failure_id"]

            #!!AI hack, to work out poor parsing for now.
            if ".  Total" not in failure_id:
                failure_id_to_count[failure_id] = failure_id_to_count.get(failure_id, 0) + int(count)
                failure_id_to_collection[failure_id] = collection
    logger.debug("failure_id_to_count: \n%s" % (pprint.pformat(failure_id_to_count), ))
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Go back and get failure_type for each failure_id.
    # ------------------------------------------------------------------------
    failure_id_to_failure_type = {}
    jobs = []
    for (failure_id, collection) in failure_id_to_collection.items():
        job = gevent.spawn(collection.find_one,
                           {"failure_id": failure_id})
        jobs.append(job)
    gevent.joinall(jobs)
    for ((failure_id, collection), job) in zip(failure_id_to_collection.items(), jobs):
        example_result = job.value
        if example_result and "failure_type" in example_result:
            failure_type = example_result["failure_type"]
            #!!AI another hack, parsing once gave empty strings.
            if failure_type != '':
                failure_id_to_failure_type[failure_id] = failure_type
    logger.debug("failure_id_to_failure_type: \n%s" % (pprint.pformat(failure_id_to_failure_type), ))

    failure_type_to_failure_id = {}
    for (failure_id, failure_type) in failure_id_to_failure_type.items():
        current_failure_ids = failure_type_to_failure_id.get(failure_type, [])
        current_failure_ids.append(failure_id)
        failure_type_to_failure_id[failure_type] = current_failure_ids
    logger.debug("failure_type_to_failure_id: \n%s" % (pprint.pformat(failure_type_to_failure_id), ))
    # ------------------------------------------------------------------------

    failure_type_to_count = {}
    for (failure_id, failure_type) in failure_id_to_failure_type.items():
        count = failure_id_to_count[failure_id]
        failure_type_to_count[failure_type] = failure_type_to_count.get(failure_type, 0) + count
    failure_types_and_counts = sorted(failure_type_to_count.items(), key=operator.itemgetter(0))
    failure_types_and_counts = [(base64.b64encode(failure_type), failure_type, count)
                                for (failure_type, count) in failure_types_and_counts]
    logger.debug("failure_types_and_counts: \n%s" % (pprint.pformat(failure_types_and_counts), ))

    sorted_failure_ids_and_counts = {}
    for (friendly_failure_type, failure_type, count) in failure_types_and_counts:
        failure_ids = failure_type_to_failure_id[failure_type]
        failure_ids_and_counts = [(failure_id, failure_id_to_count[failure_id]) for failure_id in failure_ids]
        sorted_elem = sorted(failure_ids_and_counts, key=operator.itemgetter(1), reverse=True)
        sorted_failure_ids_and_counts[failure_type] = sorted_elem

    failure_id_to_full_text_link = {}
    link_template = Template(r"/full_text_search_results?include_search_string=${include_search_string}&datetime_interval=${datetime_interval}&log_type=${log_type}&exclude_search_string=")
    for failure_id in failure_id_to_count:
        link = link_template.substitute(include_search_string = base64.urlsafe_b64encode(failure_id),
                                        datetime_interval = base64.urlsafe_b64encode(datetime_interval),
                                        log_type = base64.urlsafe_b64encode(log_type))
        failure_id_to_full_text_link[failure_id] = link

    template = jinja2_env.get_template('intel_error_count_results.html')
    stream = template.stream(failure_types_and_counts = failure_types_and_counts,
                             sorted_failure_ids_and_counts = sorted_failure_ids_and_counts,
                             failure_id_to_full_text_link = failure_id_to_full_text_link,
                             datetime_interval = datetime_interval)
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
        jobs = []
        for collection_name in collection_names:
            logger.debug("collection_name: %s" % (collection_name, ))
            collection = db.get_collection(collection_name)
            job = gevent.spawn(collection.group,
                               key = q_key,
                               condition = q_condition,
                               initial = q_initial,
                               reduce = q_reduce)
            jobs.append(job)
        gevent.joinall(jobs)
        for (collection_name, job) in zip(collection_names, jobs):
            collection = db.get_collection(collection_name)
            for elem in job.value:
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
                if example_result and "contents" in example_result:
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

@bottle.route('/full_text_search_results')
def full_text_search_results():
    logger = logging.getLogger("%s.full_text_search_results_get" % (APP_NAME, ))
    logger.debug("entry.")
    access_logger.debug("full_text_search_results:\n%s" % (pprint.pformat(sorted(bottle.request.items(), key=operator.itemgetter(0))), ))

    # ------------------------------------------------------------------------
    #   Validate inputs.
    # ------------------------------------------------------------------------

    valid_types = set(["ngmg_shm_messages", "ngmg_ep", "ngmg_messages", "ngmg_ms_messages"])
    valid_intervals = set(["one_hour", "six_hours", "one_day", "one_week", "one_month"])

    if len(bottle.request.forms.items()) == 0:
        query_items = dict([elem.split("=", 1) for elem in urllib.unquote(bottle.request.query_string).split("&")])
        logger.debug("GET has no query args, so let's get them ourselves. %s" % (query_items, ))
        include_search_string_encoded = query_items["include_search_string"]
        exclude_search_string_encoded = query_items["exclude_search_string"]
        log_type_encoded = query_items["log_type"]
        datetime_interval_encoded = query_items["datetime_interval"]
    else:
        logger.debug("GET has query items.")
        search_string_encoded = str(bottle.request.forms.get("search_string"))
        log_type_encoded = str(bottle.request.forms.get("log_type"))
        datetime_interval_encoded = str(bottle.request.forms.get("datetime_interval"))

    logger.debug("include_search_string_encoded: %s" % (include_search_string_encoded, ))
    logger.debug("exclude_search_string_encoded: %s" % (exclude_search_string_encoded, ))
    logger.debug("log_type_encoded: %s" % (log_type_encoded, ))
    logger.debug("datetime_interval_encoded: %s" % (datetime_interval_encoded, ))

    include_search_string = base64.urlsafe_b64decode(str(include_search_string_encoded))
    exclude_search_string = base64.urlsafe_b64decode(str(exclude_search_string_encoded))
    log_type = base64.urlsafe_b64decode(str(log_type_encoded))
    datetime_interval = base64.urlsafe_b64decode(str(datetime_interval_encoded))

    logger.debug("include_search_string: %s" % (include_search_string, ))
    logger.debug("exclude_search_string: %s" % (exclude_search_string, ))
    logger.debug("log_type: %s" % (log_type, ))
    logger.debug("datetime_interval: %s" % (datetime_interval, ))

    assert(log_type in valid_types), "%s not a valid log type from set: %s" % (log_type, valid_types)
    assert(datetime_interval in valid_intervals), "%s not a valid datetime_interval from set: %s" % (datetime_interval, valid_intervals)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Parse the search string.
    # ------------------------------------------------------------------------
    parser = QueryParser("content", None)
    query = parser.parse(include_search_string)
    if type(query) == whoosh.query.Or:
        logger.debug("query is OR type.")
        query_string = [(elem[1], ) for elem in query.all_terms()]
    elif type(query) == whoosh.query.And:
        logger.debug("query is AND type.")
        query_string = [tuple(elem[1] for elem in query.all_terms())]
    else:
        logger.debug("query is unknown type.")
        query_string = [query.all_terms()]
    logger.debug("query_string: %s" % (query_string, ))
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Tokenize the search string.
    # ------------------------------------------------------------------------
    analyzer = StandardAnalyzer()
    include_tokens = []
    for elem in analyzer(unicode(include_search_string)):
        include_tokens.append(elem.text)
    include_tokens = list(set(include_tokens))

    exclude_tokens = []
    for elem in analyzer(unicode(exclude_search_string)):
        exclude_tokens.append(elem.text)
    exclude_tokens = list(set(exclude_tokens))

    logger.debug("include_search_string: %s, exclude_search_string: %s, log_type: %s, datetime_interval: %s, include_tokens: %s, exclude_tokens: %s" % (include_search_string, exclude_search_string, log_type, datetime_interval, include_tokens, exclude_tokens))
    # ------------------------------------------------------------------------

    datetime_interval_obj = getattr(db, datetime_interval)
    collection_names = sorted(db.get_collection_names(name_filter = log_type))
    logger.debug("collection_names: %s" % (collection_names, ))
    log_data = []
    for collection_name in collection_names:
        collection = db.get_collection(collection_name)
        cursor = db.get_full_text_search_of_logs(collection = collection,
                                                 include_search_argument = include_tokens,
                                                 exclude_search_argument = exclude_tokens,
                                                 datetime_interval = datetime_interval_obj,
                                                 query_argument = query_string)
        log_data.append((collection_name, cursor))

    template = jinja2_env.get_template('full_text_search_results.html')
    stream = template.stream(log_data = log_data)
    for chunk in stream:
        yield chunk

@bottle.route('/full_text_search_results', method='POST')
def full_text_search_results():
    logger = logging.getLogger("%s.full_text_search_results_post" % (APP_NAME, ))
    logger.debug("entry.")
    access_logger.debug("full_text_search_results:\n%s" % (pprint.pformat(sorted(bottle.request.items(), key=operator.itemgetter(0))), ))

    # ------------------------------------------------------------------------
    #   Validate inputs.
    # ------------------------------------------------------------------------
    valid_types = set(["ngmg_shm_messages", "ngmg_ep", "ngmg_messages", "ngmg_ms_messages"])
    valid_intervals = set(["one_hour", "six_hours", "one_day", "one_week", "one_month"])

    include_search_string = str(bottle.request.forms.get("include_search_string"))
    exclude_search_string = str(bottle.request.forms.get("exclude_search_string"))
    log_type = str(bottle.request.forms.get("log_type"))
    datetime_interval = str(bottle.request.forms.get("datetime_interval"))

    assert(log_type in valid_types), "%s not in valid_types %s" % (log_type, valid_types)
    assert(datetime_interval in valid_intervals), "%s not in valid_intervals %s" % (datetime_interval, valid_intervals)
    # ------------------------------------------------------------------------

    include_search_string_encoded = base64.urlsafe_b64encode(include_search_string)
    exclude_search_string_encoded = base64.urlsafe_b64encode(exclude_search_string)
    log_type_encoded = base64.urlsafe_b64encode(log_type)
    datetime_interval_encoded = base64.urlsafe_b64encode(datetime_interval)
    data = {"include_search_string": include_search_string_encoded,
            "exclude_search_string": exclude_search_string_encoded,
            "log_type": log_type_encoded,
            "datetime_interval": datetime_interval_encoded}
    logger.debug("data: %s" % (data, ))
    data_items = ["=".join([key, value]) for (key, value) in data.items()]
    data_addendum = "&".join(data_items)
    redirect_destination = r"/full_text_search_results?%s" % (data_addendum, )
    logger.debug("redirecting to: %s" % (redirect_destination, ))
    bottle.redirect(redirect_destination)

# ----------------------------------------------------------------------------
#   Static files.
# ----------------------------------------------------------------------------
@bottle.route('/favicon.ico')
def server_static():
    return bottle.static_file('favicon.ico', root=ROOT_PATH)

@bottle.route('/humans.txt')
def server_static():
    return bottle.static_file('humans.txt', root=ROOT_PATH)

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

