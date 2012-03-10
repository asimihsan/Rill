import gevent
from gevent import monkey; monkey.patch_all()
from socketio import SocketIOServer
from gevent_zeromq import zmq
import requests
import json

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

# ----------------------------------------------------------------------------
#   Logging.
# ----------------------------------------------------------------------------
import logging
import logging.handlers
import platform
APP_NAME = "rill_real_time_stream"
if platform.system() == "Windows":
    LOG_FILENAME = r"I:\logs\%s.log" % (APP_NAME, )
else:
    LOG_FILENAME = r"/var/log/%s.log" % (APP_NAME, )
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

global socket_io_server
socket_io_server = None

context = zmq.Context()

def get_list_of_services():
    r = requests.get("http://127.0.0.1:10000/list_of_services")
    r.raise_for_status()
    services = json.loads(r.text)
    return services

class Application(object):
    def __init__(self):
        logger = logging.getLogger("%s.Application.__init__" % (APP_NAME, ))
        logger.debug("entry.")

    def setup_zeromq_bindings(self):
        self.services = get_list_of_services()
        logger.debug("services: %s" % (self.services, ))
        elems = [(key, value) for (key, value) in self.services.items() if "leo" in key]
        names = [key for (key, value) in elems]
        bindings = [value for (key, value) in elems]
        sockets = []
        for binding in bindings:
            socket = context.socket(zmq.SUB)
            socket.setsockopt(zmq.SUBSCRIBE, "")
            socket.setsockopt(zmq.HWM, 1000)
            socket.connect(binding)
            sockets.append(socket)
        return (names, bindings, sockets)

    def __call__(self, environ, start_response):
        logger = logging.getLogger("%s.Application" % (APP_NAME, ))
        logger.debug("environ: %s, start_response: %s" % (environ, start_response))

        path = environ['PATH_INFO'].strip('/')
        assert(path.startswith("socket.io"))
        conn = environ['socketio']
        logger.debug("waiting for session...")
        while True:
            if not conn.session:
                gevent.sleep(0.01)
                continue
            break
        logger.debug("session available.")

        (names, bindings, sockets) = self.setup_zeromq_bindings()
        names_bindings_sockets = zip(names, bindings, sockets)
        poller = zmq.Poller()
        logger.debug("binding zeromq sockets")
        for socket in sockets:
            poller.register(socket, zmq.POLLIN)
        #logger.debug("starting heartbeat.")
        #conn.start_heartbeat()
        logger.debug("starting stream")
        while True:
            if conn.session.connected == False:
                break
            logger.debug("session: %s" % (conn.session, ))
            poll_sockets = dict(poller.poll(timeout=1000))
            if len(poll_sockets) == 0:
                continue
            gevent.sleep(0.01)  # !!AI haha, why do I need this?
            for (name, binding, socket) in names_bindings_sockets:
                if socket in poll_sockets and poll_sockets[socket] == zmq.POLLIN:
                    msg = socket.recv()
                    msg_obj = json.loads(msg)
                    #logger.debug("name: %s, contents: %s" % (name, msg_obj["contents"]))
                    conn.send(msg_obj["contents"])
            logger.debug("receiving msg...")
            msg = conn.receive()
            if msg:
                logger.debug("got a message: %s" % (msg, ))
        logger.debug("connection lost.")
        for socket in sockets:
            socket.setsockopt(zmq.LINGER, 0)
            socket.close()

@bottle.route("/real_time_stream")
def real_time_stream():
    logger = logging.getLogger("%s.real_time_stream" % (APP_NAME, ))
    logger.debug("entry.")
    global socket_io_server
    if not socket_io_server:
        logger.debug("creating socket.io server")
        socket_io_server = get_socket_io_server()
        socket_io_server.start()
    template = jinja2_env.get_template('real_time_stream.html')
    stream = template.stream()
    for chunk in stream:
        yield chunk

def get_socket_io_server():
    socket_io_server = SocketIOServer(('127.0.0.1', 8081),
                                      Application(),
                                      namespace="socket.io",
                                      policy_server=False)
    return socket_io_server
