#!/usr/bin/env python2.7

import os
import sys
import bottle
import jinja2

ROOT_PATH = os.path.abspath(os.path.join(__file__, os.pardir))

# ----------------------------------------------------------------------------
#   Templates.
# ----------------------------------------------------------------------------
import jinja2
# ----------------------------------------------------------------------------

@bottle.route('/')
def index():
    data = {}
    return bottle.jinja2_template("index.html", data=data)

# ----------------------------------------------------------------------------
#   Static files.
# ----------------------------------------------------------------------------
@bottle.route('/favicon.ico')
def server_static():
    return bottle.static_file('favicon.ico', root=ROOT_PATH)

@bottle.route('/css/<filename>')
def server_css_static(filename):
    return bottle.static_file(filename, root=os.path.join(ROOT_PATH, "css"))

@bottle.route('/js/<filepath:path>')
def server_js_static(filepath):
    return bottle.static_file(filepath, root=os.path.join(ROOT_PATH, "js"))
# ----------------------------------------------------------------------------

bottle.debug(True)
bottle.run(host="mink", port=8080, reloader=True, interval=0.5)

