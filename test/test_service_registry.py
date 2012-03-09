#!/usr/bin/env python2.7

import requests
import pprint
import json

BASE_URL = "http://127.0.0.1:10000"
LIST_OF_SERVICES_URL = "%s/list_of_services" % (BASE_URL, )
ADD_SERVICE_URL = "%s/add_service" % (BASE_URL, )
DELETE_SERVICE_URL = "%s/delete_service" % (BASE_URL, )
GET_SERVICE_URL = "%s/get_service" % (BASE_URL, )

def test_list_of_services():
    r = requests.get(LIST_OF_SERVICES_URL)
    assert(r.status_code == 200)
    return json.loads(r.text)

def add_service(service_name, service_value):
    data = {"service_data": json.dumps({service_name: service_value})}
    r = requests.post(ADD_SERVICE_URL, data=data)
    assert(r.status_code == 200)

def delete_service(service_name):
    data = {"service_name": service_name}
    r = requests.post(DELETE_SERVICE_URL, data=data)
    assert(r.status_code == 200)

def get_service(service_name, expect_return_code = 200):
    #r = requests.get(GET_SERVICE_URL, data={"service_name": service_name})
    r = requests.get(GET_SERVICE_URL + "?service_name=%s" % (service_name, ))
    assert(r.status_code == expect_return_code)
    return r.text

if __name__ == "__main__":
    print "list initially empty"
    assert(test_list_of_services() == {})

    print "add service1"
    add_service("service1", "tcp://127.0.0.1:50000")

    print "check service1 can be gotten individually"
    rc = get_service("service1")
    assert(rc == "tcp://127.0.0.1:50000"), "rc is: %s" % (rc, )

    print "check list of services is exactly service1"
    rc = test_list_of_services()
    assert(rc == {"service1": "tcp://127.0.0.1:50000"}), "rc is: %s" % (rc, )

    print "delete service1"
    delete_service("service1")
    print "check service1, when gotten, is not present."
    get_service("service1", expect_return_code=404)
    print "service list finally empty."
    assert(test_list_of_services() == {})

    print "finished successfully"

