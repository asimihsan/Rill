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
import operator

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
    from constants import *
except:
    logger.exception("unhandled exception during constant creation.")
    raise
# -----------------------------------------------------------------------------

from utilities import GlobalConfig, BoxConfig, LogFile, ParserConfig, StoreConfig, parse_config_files

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

    rv = parse_config_files()
    global_config = rv["global_config"]
    box_configs = rv["box_configs"]
    parser_configs = rv["parser_configs"]
    store_configs = rv["store_configs"]

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
        proc = start_process(service_registry_cmd, verbose)
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
        proc = start_process(masspinger_cmd, verbose)
        masspinger_process = Process(masspinger_cmd, "masspinger", proc)
        all_processes.append(masspinger_process)

        masspinger_tap_cmd = masspinger_tap_template.substitute(executable = masspinger_tap_filepath,
                                                                masspinger_zeromq_bind = masspinger_zeromq_bind).strip()
        masspinger_tap_cmd += " --verbose"
        proc = start_process(masspinger_tap_cmd, verbose)
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

                # ------------------------------------------------------------
                #   One robust_ssh_tap instance for the real-time contents
                #   of the log.
                # ------------------------------------------------------------
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

                # Register the parser PUBLISH bindings with the service registry.
                add_service_to_service_registry(port = service_registry_port,
                                                service_name = "%s_%s" % (host, parser_name),
                                                service_value = parser_zeromq_bind)
                # ------------------------------------------------------------

                # ------------------------------------------------------------
                #   One reconcile_log instance to make sure the portions
                #   of the log outputted during network outages are
                #   in there too.
                # ------------------------------------------------------------
                reconcile_log_executable = python_executable + ' ' + reconcile_log_filepath
                masspinger_zeromq_bind = "tcp://127.0.0.1:%s" % (masspinger_port, )
                ssh_tap_zeromq_bind = "tcp://127.0.0.1:%s" % (ssh_tap_port + 1, )
                parser_zeromq_bind = "tcp://127.0.0.1:%s" % (parser_port + 1, )
                parser_name = parser_config.get_parser_name()
                host = box_config.get_dns_hostname()

                log_file_fullpath = log_file.get_full_path()
                log_file_fullpath = log_file_fullpath.replace(r"/", r"\/")
                command = """for file in \\\\\\`ls %s*\\\\\\`; do nice -n 19 ionice -c3 cat \\\\\\$file; done""" % (log_file_fullpath, )

                username = box_config.get_username()
                password = box_config.get_password()
                collection_name = "%s_%s" % (host, parser_name)
                command = reconcile_log_template.substitute( \
                        executable = reconcile_log_executable,
                        masspinger_zeromq_bind = masspinger_zeromq_bind,
                        ssh_tap_zeromq_bind = ssh_tap_zeromq_bind,
                        parser_zeromq_bind = parser_zeromq_bind,
                        parser_name = parser_name,
                        results_zeromq_bind = results_zeromq_bind,
                        host = host,
                        command = command,
                        username = username,
                        password = password,
                        collection_name = collection_name).strip()
                if global_config.get_reconcile_log_verbose():
                    command += " --verbose"
                commands.append((command, host, parser_name, parser_zeromq_bind))
                # ------------------------------------------------------------

                ssh_tap_port += 5
                parser_port += 5
                results_port += 5
        # --------------------------------------------------------------------

        logger.debug("robust_ssh_tap commands:\n%s" % (pprint.pformat([elem[0] for elem in commands]), ))
        for (command, host, parser_name, results_zeromq_bind) in commands:
            #logger.debug("robust_ssh_tap command: %s" % (command, ))
            proc = start_process(command, verbose)
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
        raise
    except:
        logger.exception("unhandled exception")
        raise
    finally:
        logger.debug("kill all the processes.")
        for process in all_processes:
            terminate_process(process.get_process_object(),
                              process.get_process_name(),
                              kill=False)
        time.sleep(3)
        for process in all_processes:
            killtree(process.get_process_object().pid)

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

def start_process(command_line, verbose=False):
    logger = logging.getLogger("%s.start_process" % (APP_NAME, ))
    logger.debug("Starting: %s. verbose: %s" % (command_line, verbose))
    null_fp = open(os.devnull, "w")
    if platform.system() == "Linux":
        if verbose:
            proc = subprocess.Popen(command_line,
                                    shell=True)
        else:
            proc = subprocess.Popen(command_line,
                                    shell=True,
                                    stdout=null_fp,
                                    stderr=null_fp)
    else:
        # To allow sending CTRL_C_EVENT signals to the process set
        # a Windows-only creation flag.
        if verbose:
            proc = subprocess.Popen(command_line,
                                    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            proc = subprocess.Popen(command_line,
                                    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP,
                                    stdout=null_fp,
                                    stderr=null_fp)
    return proc

def terminate_process(process_object, process_name, kill=False):
    logger = logging.getLogger("%s.terminate_process" % (APP_NAME, ))
    logger.info("Terminating: %s" % (process_name, ))
    if not process_object:
        return True
    try:
        if platform.system() == "Linux":
            process_object.terminate()
        else:
            process_object.send_signal(signal.CTRL_C_EVENT)
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
