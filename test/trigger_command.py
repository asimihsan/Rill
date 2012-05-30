#!/usr/bin/env python2.7

# ---------------------------------------------------------------------------
# Copyright (c) 2011 Asim Ihsan (asim dot ihsan at gmail dot com)
# Distributed under the MIT/X11 software license, see the accompanying
# file license.txt or http://www.opensource.org/licenses/mit-license.php.
# ---------------------------------------------------------------------------

import os
import sys
import zmq
import pprint
from string import Template
import json
import requests
import argparse
import re
import operator
import subprocess
import multiprocessing

# ---------------------------------------------------------------------------
#   Constants.
# ---------------------------------------------------------------------------
APP_NAME = 'trigger_command'
LOG_FILENAME = r'/var/log/rill/trigger_command.log'
SSH_TAP_PATH = r"/root/ai/Rill/bin/linux/ssh_tap"
SSH_TAP_COMMAND = Template("${ssh_tap_path} -H \"${hostname}\" -C \"${command}\"")
SERVICE_REGISTRY_GET_URI = "http://mink:10000/list_of_services"
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
#   Logging.
# ---------------------------------------------------------------------------
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
# ---------------------------------------------------------------------------

def get_services(service_name_filter):
    request = requests.get(SERVICE_REGISTRY_GET_URI)
    request_decoded = json.loads(request.text)
    rv = []
    for (service_name, service_binding) in request_decoded.items():
        if re.search(service_name_filter, service_name):
            rv.append(Service(service_name, service_binding))
    rv.sort()
    return rv

def parse_args():
    parser = argparse.ArgumentParser("Trigger commands over SSH based on log output.")
    parser.add_argument("--hostname_regexp",
                        dest="hostname_regexp",
                        metavar="REGULAR EXPRESSION",
                        required=True,
                        help="Regular expression to choose what hosts we subscribe to.")
    parser.add_argument("--command",
                        dest="command",
                        metavar="STRING",
                        required=True,
                        help="Command to execute when we see a log.")
    parser.add_argument("--log_regexp",
                        dest="log_regexp",
                        metavar="Regular expression to determine a matching log.",
                        required=True,
                        help="ZeroMQ binding we use to parse the logs.")
    parser.add_argument("--verbose",
                        dest="verbose",
                        action='store_true',
                        default=False,
                        help="Enable verbose debug mode.")
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")
    return args

class Service(object):
    def __init__(self, service_name, service_binding):
        self.service_name = service_name
        self.service_binding = service_binding
        self.dns_hostname = self.service_name.partition("_")[0]

    def __cmp__(self, other):
        return cmp(self.service_name, other.service_name)

    def __hash__(self):
        return hash(self.service_name)

    def __repr__(self):
        return "{Service: service_name=%s, service_binding=%s, dns_hostname=%s" % (self.service_name, self.service_binding, self.dns_hostname)

def execute_command(hostname, command):
    logger = logging.getLogger("%s.hostname" % (APP_NAME, ))
    logger.debug("entry. command: %s" % (command, ))
    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    stdout_value = proc.communicate()[0]
    logger.info("stdout: %s" % (stdout_value, ))

def main():
    logger = logging.getLogger("%s.main" % (APP_NAME, ))
    logger.debug("entry.")

    args = parse_args()
    logger.debug("command-line arguments:\n%s" % (pprint.pformat(args), ))

    log_re = re.compile(args.log_regexp)
    services = get_services(args.hostname_regexp)
    services_lookup = dict([(elem.service_name, elem) for elem in services])
    logger.debug("services:\n%s" % (pprint.pformat(services), ))

    context = zmq.Context(1)
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.SUBSCRIBE, "")
    for service in services:
        socket.connect(service.service_binding)

    while 1:
        incoming = socket.recv()
        try:
            incoming_decoded = json.loads(incoming)
        except:
            continue
        if not log_re.search(str(incoming_decoded["contents"])):
            continue
        logger.debug("incoming: \n%s" % (pprint.pformat(incoming_decoded), ))
        box_name = str(incoming_decoded["box_name"])
        service = services_lookup[box_name]
        hostname = service.dns_hostname
        command = SSH_TAP_COMMAND.substitute(ssh_tap_path = SSH_TAP_PATH,
                                             hostname = hostname,
                                             command = args.command)
        logger.info("Hostname hit: '%s'. Executing command: '%s'" % (hostname, command))
        p = multiprocessing.Process(target = execute_command,
                                    args = (hostname, command))
        p.start()

if __name__ == "__main__":
    logger.info("starting")
    main()


