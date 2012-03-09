#!/usr/bin/env python2.7

import argparse
import bottle
import json

# -----------------------------------------------------------------------------
#   Logging.
# -----------------------------------------------------------------------------
APP_NAME = "service_registry"
import logging
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)
# -----------------------------------------------------------------------------

class Service(object):
    def __init__(self, name, publish_binding):
        self.name = name
        self.publish_binding = publish_binding

    def __eq__(self, other):
        return eq(self.name, other.name)

    def __hash__(self):
        return hash(self.name)

    def get_dict_representation(self):
        return {self.name: self.publish_binding}

    def __str__(self):
        return "{Service: %s}" % (self.get_dict_representation(), )

class ServiceEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Service):
            return obj.get_dict_representation()
        return JSONEncode.default(self, obj)

data = {}

@bottle.route('/list_of_services')
def list_of_services():
    logger = logging.getLogger("%s.list_of_services" % (APP_NAME, ))
    logger.debug("entry.")
    objs = [elem.get_dict_representation().items()[0] for elem in data.itervalues()]
    logger.debug("objs: %s" % (objs, ))
    return_value = dict(objs)
    logger.debug("returning: %s" % (return_value, ))
    return json.dumps(return_value)

@bottle.route('/add_service', method='POST')
def add_service():
    logger = logging.getLogger("%s.add_service" % (APP_NAME, ))
    logger.debug("entry.")

    service_data  = str(bottle.request.forms.get("service_data"))
    logger.debug("service_data: %s" % (service_data, ))

    service_dict = json.loads(service_data)
    assert(len(service_dict.items()) == 1)
    (service_name, service_value) = service_dict.items()[0]
    service_obj = Service(service_name, service_value)
    data[service_name] = service_obj

@bottle.route('/delete_service', method='POST')
def delete_service():
    logger = logging.getLogger("%s.delete_service" % (APP_NAME, ))
    logger.debug("entry.")

    service_name = str(bottle.request.forms.get("service_name"))
    logger.debug("service_name: %s" % (service_name, ))
    if service_name not in data:
        logger.debug("service %s doesn't exist" % (service_name, ))
        raise bottle.HTTPError(code=404)
    data.pop(service_name)

@bottle.route('/get_service')
def get_service():
    logger = logging.getLogger("%s.get_service" % (APP_NAME, ))
    logger.debug("entry.")

    service_name = str(bottle.request.query.get("service_name"))
    logger.debug("service_name: %s" % (service_name, ))

    if service_name not in data:
        logger.debug("service %s doesn't exist" % (service_name, ))
        raise bottle.HTTPError(code=404)
    return_value = data[service_name].publish_binding
    logger.debug("returning: %s" % (return_value, ))
    return return_value

def main(port,
        verbose):
    logger.debug("port: %s" % (port, ))
    logger.debug("verbose: %s" % (verbose, ))

    bottle.debug(True)
    bottle.run(host="0.0.0.0",
               port=port,
               reloader=True,
               interval=0.5,
               server="auto")

if __name__ == "__main__":
    logger.debug("starting.")
    parser = argparse.ArgumentParser("Track ZeroMQ PUBLISH bindings")
    parser.add_argument("--port",
                        dest="port",
                        metavar="PORT_NUMBER",
                        required=True,
                        help="What HTTP port to bind to.")
    parser.add_argument("--verbose",
                        dest="verbose",
                        action='store_true',
                        default=True,
                        help="Enable verbose debug mode.")
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")
    main(port = args.port,
         verbose = args.verbose)

