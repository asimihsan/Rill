#!/usr/bin/env python2.7

import os
import sys
import time
import math
import pymongo.errors
import logging
from glob import glob
import pprint
import yaml
import operator

from constants import *

APP_NAME = "utilities"
logger = logging.getLogger()

# Retry decorator with exponential backoff
pymongo_exception_string = "pymongo.errors.AutoReconnect exception"
def retry(tries=5, delay=0.1, backoff=2, rv_on_failure=None):
    """Retries a function or method until it returns True.

    delay sets the initial delay in seconds, and backoff sets the factor by which
    the delay should lengthen after each failure. backoff must be greater than 1,
    or else it isn't really a backoff. tries must be at least 0, and delay
    greater than 0.

    Although this can be modified, to date this is only intended to retry
    MongoDB AutoReconnect exceptions.

    Reference:
    http://wiki.python.org/moin/PythonDecoratorLibrary#Retry"""

    if backoff <= 1:
        raise ValueError("backoff must be greater than 1")

    if tries < 0:
        raise ValueError("tries must be 0 or greater")

    if delay <= 0:
        raise ValueError("delay must be greater than 0")

    def deco_retry(f):
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay # make mutable
            try:
                rv = f(*args, **kwargs) # first attempt
            except pymongo.errors.AutoReconnect:
                rv = pymongo_exception_string
            while mtries > 0:
                if rv != pymongo_exception_string: # Done on success
                    return rv
                mtries -= 1      # consume an attempt
                time.sleep(mdelay) # wait...
                mdelay *= backoff  # make future wait longer
                try:
                    rv = f(*args, **kwargs) # Try again
                except pymongo.errors.AutoReconnect:
                    rv = pymongo_exception_string
            return rv_on_failure # Ran out of tries :-(

        return f_retry # true decorator -> decorated function
    return deco_retry  # @retry(arg[, ...]) -> true decorator

class GlobalConfig(object):
    def __init__(self, global_config_tree):
        self.valid = False
        self.parse(global_config_tree)

    def validate_tree(self, global_config_tree):
        logger = logging.getLogger("%s.GlobalConfig.validate_tree" % (APP_NAME, ))
        logger.debug("entry.")

        for root_key in ["port_ranges",
                         "production",
                         "service_registry_verbose",
                         "masspinger_verbose",
                         "robust_ssh_tap_verbose",
                         "reconcile_log_verbose"]:
            if root_key not in global_config_tree:
                logger.error("'%s' missing" % (root_key, ))
                return False
        port_ranges = global_config_tree["port_ranges"]
        for port_range_key in ["service_registry_port",
                               "masspinger_port",
                               "ssh_tap_port_start",
                               "parser_port_start",
                               "results_port_start"]:
            if port_range_key not in port_ranges:
                logger.error("'%s' not in port_ranges" % (port_range_key, ))
                return False
        return True

    def parse(self, global_config_tree):
        if not self.validate_tree(global_config_tree):
            return None
        self.service_registry_verbose = global_config_tree["service_registry_verbose"]
        self.masspinger_verbose = global_config_tree["masspinger_verbose"]
        self.robust_ssh_tap_verbose = global_config_tree["robust_ssh_tap_verbose"]
        self.reconcile_log_verbose = global_config_tree["reconcile_log_verbose"]
        self.production = global_config_tree["production"]
        port_ranges = global_config_tree["port_ranges"]
        self.service_registry_port = port_ranges["service_registry_port"]
        self.masspinger_port = port_ranges["masspinger_port"]
        self.ssh_tap_port_start = port_ranges["ssh_tap_port_start"]
        self.parser_port_start = port_ranges["parser_port_start"]
        self.results_port_start = port_ranges["results_port_start"]
        self.valid = True

    def get_service_registry_port(self):
        return self.service_registry_port

    def get_masspinger_port(self):
        return self.masspinger_port

    def get_parser_port_start(self):
        return self.parser_port_start

    def get_ssh_tap_port_start(self):
        return self.ssh_tap_port_start

    def get_results_port_start(self):
        return self.results_port_start

    def get_service_registry_verbose(self):
        return self.service_registry_verbose

    def get_masspinger_verbose(self):
        return self.masspinger_verbose

    def get_robust_ssh_tap_verbose(self):
        return self.robust_ssh_tap_verbose

    def get_reconcile_log_verbose(self):
        return self.reconcile_log_verbose

    def get_production(self):
        return self.production

class BoxConfig(object):
    def __init__(self, box_config_tree):
        self.valid = False
        self.parse(box_config_tree)

    def validate_tree(self, box_config_tree):
        logger = logging.getLogger("%s.BoxConfig.validate_tree" % (APP_NAME, ))
        logger.debug("entry.")

        for root_key in ["friendly name",
                         "dns hostname",
                         "username",
                         "password",
                         "type",
                         "production"]:
            if root_key not in box_config_tree:
                logger.error("'%s' missing" % (root_key, ))
                return False
        log_files = box_config_tree.get("log files", [])
        for log_file in log_files:
            for root_key in ["name",
                             "type",
                             "full path"]:
                if root_key not in log_file:
                    logger.error("'%s' missing from log_file" % (root_key, ))
                    return False
        commands = box_config_tree.get("commands", [])
        for command in commands:
            for root_key in ["name",
                             "type",
                             "command"]:
                if root_key not in command:
                    logger.error("'%s' missing from command" % root_key)
                    return False
        return True

    def parse(self, box_config_tree):
        if not self.validate_tree(box_config_tree):
            return None
        self.friendly_name = box_config_tree["friendly name"]
        self.dns_hostname = box_config_tree["dns hostname"]
        self.username = box_config_tree["username"]
        self.password = box_config_tree["password"]
        self.type = box_config_tree["type"]
        self.production = box_config_tree["production"]
        self.log_files = []
        for log_file in box_config_tree.get("log files", []):
            log_file = LogFile(log_file["name"],
                               log_file["type"],
                               log_file["full path"])
            self.log_files.append(log_file)
        self.commands = []
        for command in box_config_tree.get("commands", []):
            command = Command(command["name"],
                              command["type"],
                              command["command"])
            self.commands.append(command)
        self.valid = True

    def get_dns_hostname(self):
        return self.dns_hostname

    def get_log_files(self):
        return self.log_files

    def get_commands(self):
        return self.commands

    def get_type(self):
        return self.type

    def get_username(self):
        return self.username

    def get_password(self):
        return self.password

    def get_production(self):
        return self.production

    def get_tail_command(self):
        if self.type == "NGMG":
            return "tail -f --follow=name"
        else:
            return "tail -f"

    def __str__(self):
        return "{BoxConfig: dns_hostname=%s, type=%s, log_files=%s, commands=%s}" % (self.dns_hostname, self.type, self.log_files, self.commands)

class LogFile(object):
    def __init__(self, log_name, log_type, log_full_path):
        self.log_name = log_name
        self.log_type = log_type
        self.log_full_path = log_full_path

    def get_name(self):
        return self.log_name

    def get_type(self):
        return self.log_type

    def get_full_path(self):
        return self.log_full_path

    def __str__(self):
        return "{LogFile: name=%s, type=%s, full_path=%s}" % (self.log_name, self.log_type, self.log_full_path)

    def __repr__(self):
        return str(self)

class Command(object):
    def __init__(self, command_name, command_type, command_string):
        self.command_name = command_name
        self.command_type = command_type
        self.command_string = command_string

    def get_name(self):
        return self.command_name

    def get_type(self):
        return self.command_type

    def get_string(self):
        return self.command_string

    def __str__(self):
        return "{Commmand: name=%s, type=%s, string=%s}" % (self.command_name, self.command_type, self.command_string)

    def __repr__(self):
        return str(self)

class ParserConfig(object):
    valid_parser_types = ["logfile", "command"]

    def __init__(self, parser_config_tree):
        self.valid = False
        self.parse(parser_config_tree)

    def validate_tree(self, parser_config_tree):
        logger = logging.getLogger("%s.ParserConfig.validate_tree" % (APP_NAME, ))
        logger.debug("entry. parser_config_tree: %s" % parser_config_tree)

        for root_key in ["box type",
                         "parser type",
                         "parser"]:
            if root_key not in parser_config_tree:
                logger.error("'%s' missing" % (root_key, ))
                return False
        if parser_config_tree["parser type"] not in self.valid_parser_types:
            logger.error("'parser type' %s is not valid, judging by: %s" % (parser_config_tree["parser type"], self.valid_parser_types))
            return False
        if parser_config_tree["parser type"] == "logfile":
            if "log file type" not in parser_config_tree:
                logger.error("'log file type' missing for parser of type 'logfile'")
                return False
        elif parser_config_tree["parser type"] == "command":
            if "command type" not in parser_config_tree:
                logger.error("'command type' missing for parser of type 'command'")
                return False
        return True

    def parse(self, parser_config_tree):
        if not self.validate_tree(parser_config_tree):
            return None
        self.box_type = parser_config_tree["box type"]
        self.parser_type = parser_config_tree["parser type"]
        self.log_file_type = parser_config_tree.get("log file type", None)
        self.command_type = parser_config_tree.get("command type", None)
        self.parser = parser_config_tree["parser"]
        self.valid = True

    def get_parser_name(self):
        return self.parser

    def get_parser_type(self):
        return self.parser_type

    def get_command_type(self):
        return self.command_type

    def get_log_file_type(self):
        return self.log_file_type

    def get_box_type(self):
        return self.box_type

class StoreConfig(object):
    def __init__(self, store_config_tree):
        self.valid = False
        self.parse(store_config_tree)

    def validate_tree(self, store_config_tree):
        logger = logging.getLogger("%s.StoreConfig.validate_tree" % (APP_NAME, ))
        logger.debug("entry.")

        for root_key in ["name",
                         "hostname"]:
            if root_key not in store_config_tree:
                logger.error("'%s' missing" % (root_key, ))
                return False
        return True

    def parse(self, store_config_tree):
        if not self.validate_tree(store_config_tree):
            return None
        self.name = store_config_tree["name"]
        self.hostname = store_config_tree["hostname"]
        self.valid = True

def parse_config_files():
    # ------------------------------------------------------------------------
    #   Parse the config files.
    # ------------------------------------------------------------------------
    logger.debug("Parsing config from: %s" % (config_directory, ))
    global_config_filepath = os.path.join(config_directory, "global.config.rill")
    assert(os.path.isfile(global_config_filepath)), "Can't find global config at %s" % (global_config_filepath, )
    box_config_filepaths = glob(os.path.join(config_directory, "box", "*.config.rill"))
    parser_config_filepaths = glob(os.path.join(config_directory, "parser", "*.config.rill"))
    store_config_filepaths = glob(os.path.join(config_directory, "store", "*.config.rill"))

    logger.debug("box_configs:\n%s" % (pprint.pformat(box_config_filepaths), ))
    logger.debug("parser_configs:\n%s" % (pprint.pformat(parser_config_filepaths), ))
    logger.debug("store_configs:\n%s" % (pprint.pformat(store_config_filepaths), ))

    with open(global_config_filepath) as f:
        logger.debug("reading '%s'" % (global_config_filepath, ))
        yaml_obj = yaml.load(f.read())
    global_config = GlobalConfig(yaml_obj)
    if not global_config.valid:
        logger.error("Global config '%s' is not valid" % (global_config_filepath, ))

    box_configs = []
    for box_config_filepath in box_config_filepaths:
        with open(box_config_filepath) as f:
            logger.debug("reading '%s'" % (box_config_filepath, ))
            yaml_obj = yaml.load(f.read())
        box_config = BoxConfig(yaml_obj)
        if not box_config.valid:
            logger.error("Box config '%s' is not valid" % (box_config_filepath, ))
        box_configs.append(box_config)
    box_configs.sort(key = operator.methodcaller("get_dns_hostname"))

    parser_configs = []
    for parser_config_filepath in parser_config_filepaths:
        with open(parser_config_filepath) as f:
            logger.debug("reading '%s'" % (parser_config_filepath, ))
            yaml_obj = yaml.load(f.read())
        parser_config = ParserConfig(yaml_obj)
        if not parser_config.valid:
            logger.error("Parser config '%s' is not valid" % (parser_config_filepath, ))
        parser_configs.append(parser_config)

    store_configs = []
    for store_config_filepath in store_config_filepaths:
        with open(store_config_filepath) as f:
            logger.debug("reading '%s'" % (store_config_filepath, ))
            yaml_obj = yaml.load(f.read())
        store_config = StoreConfig(yaml_obj)
        if not store_config.valid:
            logger.error("Store config '%s' is not valid" % (store_config_filepath, ))
        store_configs.append(store_config)
    # ------------------------------------------------------------------------

    return {"global_config": global_config,
            "box_configs": box_configs,
            "parser_configs": parser_configs,
            "store_configs": store_configs}

