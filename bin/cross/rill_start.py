#!/usr/bin/env python2.7

# -----------------------------------------------------------------------------
# Copyright (c) 2011 Asim Ihsan (asim dot ihsan at gmail dot com)
# Distributed under the MIT/X11 software license, see the accompanying
# file license.txt or http://www.opensource.org/licenses/mit-license.php.
# -----------------------------------------------------------------------------

import os
import sys
import argparse
import subprocess
import time
import datetime
import json
import platform
from string import Template
import signal
from glob import glob
import pprint
import yaml
import psutil
import requests
import socket

# -----------------------------------------------------------------------------
#   Logging.
# -----------------------------------------------------------------------------
APP_NAME = "rill_start"
import logging
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)
# -----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
#   Signal handling
# ----------------------------------------------------------------------------
import signal
def soft_handler(signum, frame):
    logging.debug('Soft stop')
    sys.exit(1)
def hard_handler(signum, frame):
    logging.debug('Hard stop')
    os._exit(2)
signal.signal(signal.SIGINT, soft_handler)
signal.signal(signal.SIGTERM, hard_handler)
# ----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
#   Constants.
# -----------------------------------------------------------------------------
try:
    current_path = os.path.abspath(__file__)
    assert(os.path.isfile(current_path)), "%s not good current_path" % (current_path, )
    current_directory = os.path.split(current_path)[0]
    assert(os.path.isdir(current_directory)), "%s not good current_directory" % (current_directory, )

    root_rill_directory = os.path.abspath(os.path.join(current_directory, os.pardir, os.pardir))
    assert(os.path.isdir(root_rill_directory)), "%s not goot root_rill_directory" % (root_rill_directory, )

    assert(platform.system() in ["Linux", "Windows"]), "Only support Linux and Windows"
    if platform.system() == "Linux":
        python_executable = r"/usr/local/bin/python2.7"
    else:
        python_executable = "python.exe"

    # platform-specific bin directories
    if platform.system() == "Linux":
        bin_directory = os.path.join(root_rill_directory, "bin", "linux")
        assert(os.path.isdir(bin_directory)), "%s not good Linux bin_directory" % (bin_directory, )
        bin_extension = ""
    else:
        bin_directory = os.path.join(root_rill_directory, "bin", "win32")
        assert(os.path.isdir(bin_directory)), "%s not good Windows bin_directory" % (bin_directory, )
        bin_extension = ".exe"
    cross_bin_directory = os.path.join(root_rill_directory, "bin", "cross")
    assert(os.path.isdir(cross_bin_directory)), "%s not good cross_bin_directory" % (cross_bin_directory, )

    masspinger_filepath = os.path.join(bin_directory, "masspinger" + bin_extension)
    assert(os.path.isfile(masspinger_filepath)), "%s not good masspinger_filepath" % (masspinger_filepath, )
    masspinger_template = Template(""" "${executable}" --zeromq_bind "${masspinger_zeromq_bind}" ${hosts} """)

    config_directory = os.path.join(cross_bin_directory, "config")
    assert(os.path.isdir(config_directory)), "%s not good config_directory" % (config_directory, )

    robust_ssh_tap_filepath = os.path.join(cross_bin_directory, "robust_ssh_tap.py")
    assert(os.path.isfile(robust_ssh_tap_filepath)), "%s not good robust_ssh_tap_filepath" % (robust_ssh_tap_filepath, )
    robust_ssh_tap_template = Template(""" ${executable} --masspinger "${masspinger_zeromq_bind}" --ssh_tap "${ssh_tap_zeromq_bind}" --parser "${parser_zeromq_bind}" --parser_name "${parser_name}" --results "${results_zeromq_bind}" --host "${host}" --command "${command}" --username "${username}" --password "${password}" """)

    masspinger_tap_filepath = os.path.join(cross_bin_directory, "masspinger_tap.py")
    assert(os.path.isfile(masspinger_tap_filepath)), "%s not good masspinger_tap_filepath" % (masspinger_tap_filepath, )
    masspinger_tap_template = Template(""" ${executable} --masspinger_zeromq_bind "${masspinger_zeromq_bind}" --database "pings" """)

    service_registry_filepath = os.path.join(cross_bin_directory, "service_registry.py")
    assert(os.path.isfile(service_registry_filepath)), "%s not good service_registry_filepath" % (service_registry_filepath, )
    service_registry_template = Template(""" ${executable} --port ${port} """)

except:
    logger.exception("unhandled exception during constant creation.")
    raise
# -----------------------------------------------------------------------------

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
                         "robust_ssh_tap_verbose"]:
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
                         "log files",
                         "production"]:
            if root_key not in box_config_tree:
                logger.error("'%s' missing" % (root_key, ))
                return False
        log_files = box_config_tree["log files"]
        for log_file in log_files:
            for root_key in ["name",
                             "type",
                             "full path"]:
                if root_key not in log_file:
                    logger.error("'%s' missing from log_file" % (root_key, ))
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
        for log_file in box_config_tree["log files"]:
            log_file = LogFile(log_file["name"],
                               log_file["type"],
                               log_file["full path"])
            self.log_files.append(log_file)
        self.valid = True

    def get_dns_hostname(self):
        return self.dns_hostname

    def get_log_files(self):
        return self.log_files

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

class ParserConfig(object):
    def __init__(self, parser_config_tree):
        self.valid = False
        self.parse(parser_config_tree)

    def validate_tree(self, parser_config_tree):
        logger = logging.getLogger("%s.ParserConfig.validate_tree" % (APP_NAME, ))
        logger.debug("entry.")

        for root_key in ["box type",
                         "log file type",
                         "parser"]:
            if root_key not in parser_config_tree:
                logger.error("'%s' missing" % (root_key, ))
                return False
        return True

    def parse(self, parser_config_tree):
        if not self.validate_tree(parser_config_tree):
            return None
        self.box_type = parser_config_tree["box type"]
        self.log_file_type = parser_config_tree["log file type"]
        self.parser = parser_config_tree["parser"]
        self.valid = True

    def get_parser_name(self):
        return self.parser

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

def add_service_to_service_registry(port, service_name, service_value):
    logger = logging.getLogger("%s.add_service_to_service_registry" % (APP_NAME, ))
    logger.debug("entry. port: %s, service_name: %s, service_value: %s" % (port, service_name, service_value))
    url = "http://127.0.0.1:%s/add_service" % (port, )
    data = {"service_data": json.dumps({service_name: service_value})}
    r = requests.post(url, data=data)
    logger.debug("status code return: %s" % (r.status_code, ))
    r.raise_for_status()

def main(verbose):
    logger = logging.getLogger("%s.main" % (APP_NAME, ))
    logger.debug("entry. verbose: %s" % (verbose, ))

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

    all_processes = []
    try:
        # --------------------------------------------------------------------
        #   We'll always need one service_registry instance.
        # --------------------------------------------------------------------
        service_registry_port = global_config.get_service_registry_port()
        service_registry_cmd = service_registry_template.substitute(executable = service_registry_filepath,
                                                                    port = service_registry_port).strip()
        if global_config.get_service_registry_verbose():
            service_registry_cmd += " --verbose"
        logger.debug("service_registry_cmd: %s" % (service_registry_cmd, ))
        proc = start_process(service_registry_cmd)
        service_registry_process = Process(service_registry_cmd, "service_registry", proc)
        all_processes.append(service_registry_process)
        time.sleep(2)
        # --------------------------------------------------------------------


        # --------------------------------------------------------------------
        #   We will always need one masspinger object monitoring all hosts.
        #   Let's get it running now.
        # --------------------------------------------------------------------
        masspinger_port = global_config.get_masspinger_port()
        masspinger_zeromq_bind = "tcp://*:%s" % (masspinger_port, )
        hostnames = []
        is_global_production = global_config.get_production()
        for box_config in box_configs:
            logger.debug("box_config: %s" % (box_config, ))
            if is_global_production and not box_config.get_production():
                logger.debug("Global is production, but this is a test box.")
                continue
            elif not is_global_production and box_config.get_production():
                logger.debug("Global is test, but this is a production box.")
                continue
            hostnames.append(box_config.get_dns_hostname())
        masspinger_cmd = masspinger_template.substitute(executable = masspinger_filepath,
                                                        masspinger_zeromq_bind = masspinger_zeromq_bind,
                                                        hosts = ' '.join(hostnames)).strip()
        if global_config.get_masspinger_verbose():
            masspinger_cmd += " --verbose"
        logger.debug("masspinger_cmd: %s" % (masspinger_cmd, ))
        proc = start_process(masspinger_cmd)
        masspinger_process = Process(masspinger_cmd, "masspinger", proc)
        all_processes.append(masspinger_process)

        masspinger_tap_cmd = masspinger_tap_template.substitute(executable = masspinger_tap_filepath,
                                                                masspinger_zeromq_bind = masspinger_zeromq_bind).strip()
        masspinger_tap_cmd += " --verbose"
        proc = start_process(masspinger_tap_cmd)
        masspinger_tap_process = Process(masspinger_tap_cmd, "masspinger_tap", proc)
        all_processes.append(masspinger_tap_process)

        remote_masspinger_zeromq_binding = "tcp://%s:%s" % (socket.getfqdn(), masspinger_port)
        add_service_to_service_registry(port = service_registry_port,
                                        service_name = "masspinger",
                                        service_value = remote_masspinger_zeromq_binding)
        # --------------------------------------------------------------------

        # --------------------------------------------------------------------
        #   We will need one process per log file, let's launch them.
        #
        # robust_ssh_tap_template = Template(""" "${executable}" --masspinger "${masspinger_zeromq_bind}" --ssh_tap "${ssh_tap_zeromq_bind}" --parser "${parser_zeromq_bind}" --parser_name "${parser_name}" --results "${results_zeromq_bind}" --host "${host}" --command "${command}" --username "username" --password "password" """)
        # --------------------------------------------------------------------
        robust_ssh_tap_executable = ' '.join([python_executable, "\"%s\"" % (robust_ssh_tap_filepath, )])
        masspinger_port = int(global_config.get_masspinger_port())
        ssh_tap_port = int(global_config.get_ssh_tap_port_start())
        parser_port = int(global_config.get_parser_port_start())
        results_port = int(global_config.get_results_port_start())
        commands = []
        is_global_production = global_config.get_production()
        for box_config in box_configs:
            if is_global_production and not box_config.get_production():
                logger.debug("Global is production, but this is a test box.")
                continue
            elif not is_global_production and box_config.get_production():
                logger.debug("Global is test, but this is a product box.")
                continue

            for log_file in box_config.get_log_files():
                parser_config = [config for config in parser_configs
                                 if config.get_box_type() == box_config.get_type() and
                                    log_file.get_type() == config.get_log_file_type()]
                if len(parser_config) == 0:
                    logger.error("Could not find parser for box config %s, log file %s" % (box_config, log_file))
                    continue
                if len(parser_config) > 1:
                    logger.error("Found more than one parser for box config %s, log file %s.\n%s" % (box_config, log_file, pprint.pformat(parser_config)))
                    continue
                parser_config = parser_config[0]

                masspinger_zeromq_bind = "tcp://127.0.0.1:%s" % (masspinger_port, )
                ssh_tap_zeromq_bind = "tcp://127.0.0.1:%s" % (ssh_tap_port, )
                parser_zeromq_bind = "tcp://127.0.0.1:%s" % (parser_port, )
                parser_name = parser_config.get_parser_name()
                results_zeromq_bind = "tcp://127.0.0.1:%s" % (results_port, )
                host = box_config.get_dns_hostname()
                tail_prefix = box_config.get_tail_command()
                command = "%s '%s'" % (tail_prefix, log_file.get_full_path(), )
                username = box_config.get_username()
                password = box_config.get_password()
                command = robust_ssh_tap_template.substitute( \
                        executable = robust_ssh_tap_executable,
                        masspinger_zeromq_bind = masspinger_zeromq_bind,
                        ssh_tap_zeromq_bind = ssh_tap_zeromq_bind,
                        parser_zeromq_bind = parser_zeromq_bind,
                        parser_name = parser_name,
                        results_zeromq_bind = results_zeromq_bind,
                        host = host,
                        command = command,
                        username = username,
                        password = password).strip()

                if global_config.get_robust_ssh_tap_verbose():
                    command += " --verbose"

                commands.append((command, host, parser_name, parser_zeromq_bind))
                ssh_tap_port += 5
                parser_port += 5
                results_port += 5

                # Register the parser PUBLISH bindings with the service registry.
                add_service_to_service_registry(port = service_registry_port,
                                                service_name = "%s_%s" % (host, parser_name),
                                                service_value = parser_zeromq_bind)

        logger.debug("robust_ssh_tap commands:\n%s" % (pprint.pformat([elem[0] for elem in commands]), ))
        for (command, host, parser_name, results_zeromq_bind) in commands:
            #logger.debug("robust_ssh_tap command: %s" % (command, ))
            proc = start_process(command)
            process = Process(command, "robust_ssh_tap. {host=%s, parser_name=%s}" % (host, parser_name), proc)
            all_processes.append(process)
        for (command, host, parser_name, results_zeromq_bind) in commands:
            print '-' * 79
            logger.info("{Host=%s, parser_name=%s, results_zeromq_bind=%s}" % (host, parser_name, results_zeromq_bind))
            print '-' * 79 + "\n"
        # --------------------------------------------------------------------

        while 1:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.debug("CTRL-C")
    except:
        logger.exception("unhandled exception")
    finally:
        logger.debug("kill all the processes.")
        for process in all_processes:
            terminate_process(process.get_process_object(),
                              process.get_process_name(),
                              kill=False)
        time.sleep(1)
        for process in all_processes:
            killtree(process.get_process_object().pid)
            #terminate_process(process.get_process_object(),
            #                  process.get_process_name(),
            #                  kill=True)

class Process(object):
    def __init__(self, command_line, process_name, process_object):
        self.command_line = command_line
        self.process_name = process_name
        self.process_object = process_object

    def get_process_object(self):
        return self.process_object

    def get_command_line(self):
        return self.command_line

    def get_process_name(self):
        return self.process_name

def start_process(command_line, stdout_capture=False):
    logger = logging.getLogger("%s.start_process" % (APP_NAME, ))
    logger.debug("Starting: %s" % (command_line, ))
    null_fp = open(os.devnull, "w")
    if platform.system() == "Linux":
        if stdout_capture:
            proc = subprocess.Popen(command_line,
                                    shell=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
        else:
            proc = subprocess.Popen(command_line,
                                    shell=True,
                                    stdout=null_fp,
                                    stderr=null_fp)
    else:
        # To allow sending CTRL_C_EVENT signals to the process set
        # a Windows-only creation flag.
        if stdout_capture:
            proc = subprocess.Popen(command_line,
                                    #shell=True,
                                    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP,
                                    stdout = subprocess.PIPE,
                                    stderr = subprocess.STDOUT)
        else:
            proc = subprocess.Popen(command_line,
                                    #shell=True,
                                    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP,
                                    stdout=null_fp,
                                    stderr=null_fp)
    return proc

def terminate_process(process_object, process_name, kill=False):
    logger = logging.getLogger("%s.terminate_process" % (APP_NAME, ))
    logger.debug("Terminating: %s" % (process_name, ))
    if not process_object:
        return True
    try:
        if platform.system() == "Linux":
            process_object.terminate()
        else:
            process_object.send_signal(signal.CTRL_C_EVENT)
        time.sleep(2)
        if kill:
            logger.debug("...and kill")
            process_object.kill()
        return True
    except:
        logger.exception("unhandled exception while terminating %s." % (process_name))
        return False

def killtree(pid, including_parent=True):
    logger = logging.getLogger("%s.killtree" % (APP_NAME, ))
    logger.debug("entry. pid: %s, including_parent: %s" % (pid, including_parent))
    try:
        parent = psutil.Process(pid)
    except psutil.error.NoSuchProcess:
        return False
    if len(parent.get_children()) != 0:
        for child in parent.get_children():
            logger.debug("has child: %s" % (child.pid, ))
            killtree(child.pid, including_parent=True)
    if including_parent:
        logger.debug("kill parent: %s" % (parent.pid, ))
        parent.kill()

if __name__ == "__main__":
    logger.debug("starting.")
    parser = argparse.ArgumentParser("Start the Rill framework.")
    parser.add_argument("--verbose",
                        dest="verbose",
                        action='store_true',
                        default=False,
                        help="Enable verbose debug mode for rill_start. To enable verbose mode on subsequent scripts modify the global config.")
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")

    main(verbose = args.verbose)

    logger.debug("finishing.")
