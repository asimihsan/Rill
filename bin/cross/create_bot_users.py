#!/usr/bin/env python2.7

import requests
import json
from string import Template
import pprint

# -----------------------------------------------------------------------------
#   Logging.
# -----------------------------------------------------------------------------
APP_NAME = "create_bot_users"
LOG_FILENAME = r"/var/log/rill/create_bot_users.log"
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
# -----------------------------------------------------------------------------

SERVICE_REGISTRY_URI = "http://mink:10000/list_of_services"
OPENFIRE_ADD_USER_TEMPLATE = Template("http://mink:9090/plugins/userService/userservice?type=add&secret=3YOr2Y7c&username=${username}&password=${username}&name=${username}")

def main(service_registry_uri, openfire_add_user_template):
    http_get = requests.get(SERVICE_REGISTRY_URI)
    services = json.loads(http_get.text)
    logger.info("services: \n%s" % (pprint.pformat(services), ))
    usernames = sorted(services.keys())
    for username in usernames:
        add_uri = openfire_add_user_template.substitute(username=username)
        add_get = requests.get(add_uri)
        logger.info("URI executed: %s. Response: %s" % (add_uri, add_get.text))

if __name__ == "__main__":
    main(SERVICE_REGISTRY_URI, OPENFIRE_ADD_USER_TEMPLATE)
