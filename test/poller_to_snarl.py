import os
import sys
import operator
import socket

import zmq
from zmq.eventloop import ioloop
from zmq.eventloop.zmqstream import ZMQStream
ioloop.install()

import requests
import multiprocessing
import json
import yaml
import re

import pdb
from pprint import pprint

#-----------------------------------------------------------------------------
#   Constants.
#-----------------------------------------------------------------------------
service_registry_uri = "http://mink:10000"
get_list_of_services_uri = "%s/list_of_services" % (service_registry_uri, )
server_hostname = "mink"
config_filepath = "poller_to_snarl.yaml"
#-----------------------------------------------------------------------------

class Service(object):
    def __init__(self, service_name, service_zeromq_binding, context):
        self.service_name = str(service_name)
        if self.service_name == "masspinger":
            self.hostname = None
            self.log_type = "masspinger"
            self.log_type = None
        else:
            elems = self.service_name.split("_")
            self.hostname = elems[0]
            if "-mgmt" in self.hostname:
                self.hostname = self.hostname.replace("-mgmt", "")
            self.log_type = '_'.join(elems[1:])

        if "0.0.0.0" in service_zeromq_binding:
            service_zeromq_binding = service_zeromq_binding.replace("0.0.0.0", server_hostname)
        self.service_zeromq_binding = str(service_zeromq_binding)

        self.socket = context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE, "")
        self.socket.connect(self.service_zeromq_binding)
        self.stream = ZMQStream(self.socket)
        self.stream.on_recv(self.on_recv)
        self.on_recv_callbacks = []

    def __repr__(self):
        return "{Service: service_name=%s, hostname=%s, log_type=%s, service_zeromq_binding=%s}" % (self.service_name, self.hostname, self.log_type, self.service_zeromq_binding)

    def on_recv(self, msg):
        for (function, contents_regex, message_title) in self.on_recv_callbacks:
            function(self, msg, contents_regex, message_title)

    def add_on_recv_callback(self, callback, contents_regex, message_title):
        self.on_recv_callbacks.append((callback, contents_regex, message_title))

    def clear_on_recv_callbacks(self):
        self.on_recv_callbacks = []

    def close(self):
        self.socket.close(linger = 0)

def get_list_of_services():
    r = requests.get(get_list_of_services_uri)
    assert(r.status_code == 200)
    return json.loads(r.text)

def load_config():
    assert(os.path.isfile(config_filepath))
    with open(config_filepath) as f:
        doc = yaml.load(f)
    return doc

def main():
    config = load_config()
    context = zmq.Context(1)
    snp = PySNP()
    snp.register(app_sig="rill", app_title="rill")

    # ------------------------------------------------------------------------
    #   Get a list of services from the service registry, then bind
    #   ZeroMQ sockets to them.
    # ------------------------------------------------------------------------
    list_of_services = get_list_of_services()
    services = [Service(service_name, service_zeromq_binding, context)
                for (service_name, service_zeromq_binding) in list_of_services.iteritems()]
    services.sort(key=operator.attrgetter("service_name"))
    pprint(services)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Create callbacks for the events.
    # ------------------------------------------------------------------------
    for (event_name, event_details) in config.iteritems():
        hostname_regex = re.compile(event_details["hostname_regex"])
        contents_regex = re.compile(event_details["contents_regex"])
        log_type_regex = re.compile(event_details["log_type"])
        message_title = event_details["message_title"]
        def callback(self, msg, contents_regex, message_title):
            decoded = json.loads(msg[0])
            contents = decoded["contents"]
            if contents_regex.search(contents):
                print "%s - %s" % (self, msg[0])
                snp.notify(app_sig="rill",
                           title="%s - %s" % (self.hostname, message_title),
                           text=contents)
        for service in services:
            if service.hostname is not None and \
               hostname_regex.match(service.hostname) and \
               service.log_type is not None and \
               log_type_regex.match(service.log_type):
                print "adding event_name %s to service %s" % (event_name, service)
                service.add_on_recv_callback(callback, contents_regex, message_title)
    # ------------------------------------------------------------------------

    ioloop.IOLoop.instance().start()

class PySNP(object):
    host = '127.0.0.1'
    port = 9887

    def __init__(self, **address):
        """Creates an object of pySNP."""
        if 'host' in address:
            self.host = address['host']
        if 'port' in address:
            self.port = address['port']

    def _send(self, request, errors):
        """Trys to sends the request to Snarl"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.host, self.port))
            self.sock.send(request + '\r\n')
            recv = self.sock.recv(1024).rstrip('\r\n')
            self.sock.close()
            self._response(recv, errors, request)
        except IOError:
            errors = self._error(1, 'noserver', None, None)
            self._error(2, None, errors, None)

    def _response(self, recv, errors, request):
        """Displays Snarl's response"""
        print recv
        self._error(2, None, errors, None)
        print request

    def _process(self, action, data, args):
        """Processes everything from the actions"""
        print '\nSnarl: %s' % action
        errors = self._error()
        request = 'snp://' + action
        param = ''

        # Fills data with info from args if needed
        for val in data:
            if val in args:
                data[val][2] = args[val]

        # Checks if data is required and if vals are empty
        for key, val in sorted(data.items(), key=lambda x: x[1]):
            if val[1] is True and val[2]:
                param = param + '&' + key + '=' + val[2]
            elif val[1] is True and not val[2]:
                errors = self._error(1, 'missing', errors, key)
            elif val[1] is False and val[2]:
                param = param + '&' + key + '=' + val[2]
            else:
                pass

        # Checks for errors before sending
        if not errors:
            param = param.replace('&', '?', 1)
            request = request + param
        self._send(request, errors)

    def _error(self, mode=0, issue=None, errors=None, obj=None):
        """Assigns and displays errors"""
        issue = issue or ''
        errors = errors or []
        obj = obj or ''

        if mode is 1 and issue is 'missing':
            error = "*Error: '%s' is missing.*" % obj
            errors.append(error)
        elif mode is 1 and issue is 'noserver':
            error = "*Error: Can't connect to Snarl.*"
            errors.append(error)
        elif mode is 2:
            for error in errors:
                print error
        else:
            pass
        return errors

    def register(self, app_sig='', app_title='', **args):
        """Snarl's register action"""
        action = 'register'
        data = {'app-sig': [1, True, app_sig],
                'password': [2, False, ''],
                'title': [3, True, app_title],
                'icon': [4, False, '']}
        self._process(action, data, args)

    def notify(self, app_sig='', title='', text='', **args):
        """Snarl's notify action"""
        action = 'notify'
        data = {'app-sig': [1, True, app_sig],
                'password': [2, False, ''],
                'title': [3, True, title],
                'text': [4, False, text],
                'icon': [5, False, ''],
                'id': [6, False, ''],
                'uid': [7, False, ''],
                'timeout': [8, False, ''],
                'priority': [9, False, '']}
        self._process(action, data, args)

    def addclass(self, app_sig='', cid='', cname='', **args):
        """Snarl's addclass action"""
        action = 'addclass'
        data = {'app-sig': [1, True, app_sig],
                'password': [2, False, ''],
                'title': [3, False, ''],
                'text': [4, False, ''],
                'icon': [5, False, ''],
                'id': [6, True, cid],
                'name': [7, True, cname],
                'enabled': [8, False, '']}
        self._process(action, data, args)

    def version(self, **args):
        """Snarl's version action"""
        action = 'version'
        data = {}
        self._process(action, data, args)

    def unregister(self, app_sig='', **args):
        """Snarl's unregister action"""
        action = 'unregister'
        data = {'app-sig': [1, True, app_sig],
                'password': [2, False, '']}
        self._process(action, data, args)

if __name__ == "__main__":
    main()
