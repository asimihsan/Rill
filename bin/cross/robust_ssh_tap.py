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

import zmq
from zmq.eventloop.ioloop import IOLoop, PeriodicCallback
from zmq.eventloop.zmqstream import ZMQStream

# -----------------------------------------------------------------------------
#   Logging.
# -----------------------------------------------------------------------------
APP_NAME = "robust_ssh_tap"
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

    ssh_tap_filepath = os.path.join(bin_directory, "ssh_tap" + bin_extension)
    if not (os.path.isfile(ssh_tap_filepath)):
        ssh_tap_filepath = os.path.join(cross_directory, "ssh_tap.py")
    assert(os.path.isfile(ssh_tap_filepath)), "%s not good ssh_tap_filepath" % (ssh_tap_filepath, )
    ssh_tap_template = Template(""" "${executable}" --host "${host}" --command "${command}" --username "${username}" --password "${password}" --zeromq_bind "${zeromq_bind}" """)

    # platform-specific parser templates
    parser_template = Template(""" ${executable} --ssh_tap "${ssh_tap_zeromq_bind}" --results "${parser_zeromq_bind}" """)

except:
    logger.exception("unhandled exception during constant creation.")
    raise
# -----------------------------------------------------------------------------

def main(masspinger_zeromq_binding,
         ssh_tap_zeromq_binding,
         parser_zeromq_binding,
         parser_name,
         results_zeromq_binding,
         host,
         command,
         username,
         password,
         timeout,
         verbose):
    logger = logging.getLogger("%s.main.%s.%s" % (APP_NAME, host, parser_name))
    logger.debug("entry.")
    logger.debug("masspinger_zeromq_binding: %s" % (masspinger_zeromq_binding, ))
    logger.debug("ssh_tap_zeromq_binding: %s" % (ssh_tap_zeromq_binding, ))
    logger.debug("parser_zeromq_binding: %s" % (parser_zeromq_binding, ))
    logger.debug("parser_name: %s" % (parser_name, ))
    logger.debug("results_zeromq_binding: %s" % (results_zeromq_binding, ))
    logger.debug("host: %s" % (host, ))
    logger.debug("command: %s" % (command, ))
    logger.debug("username: %s" % (username, ))
    logger.debug("timeout: %s" % (timeout, ))
    logger.debug("verbose: %s" % (verbose, ))

    # ------------------------------------------------------------------------
    #   Validate inputs.
    # ------------------------------------------------------------------------

    # parsers are in the bin directories and the filename without extension, if
    # there is an extension, ends with "_parser". Find a list of all parsers
    # and confirm the input parser exists. We prefer binary parsers to cross
    # platform parsers.
    #
    # cross_parsers are cross-platform parsers written in Python.
    # bin_parers are binary parsers.
    all_possible_parsers = []

    cross_parser_glob = os.path.join(cross_bin_directory, "*_parser.py")
    cross_parsers = [os.path.abspath(elem) for elem in glob(cross_parser_glob)]
    logger.debug("cross_parsers:\n%s" % (pprint.pformat(cross_parsers), ))

    bin_parser_glob = os.path.join(bin_directory, "*_parser" + bin_extension)
    bin_parsers = [os.path.abspath(elem) for elem in glob(bin_parser_glob)]
    logger.debug("bin_parsers:\n%s" % (pprint.pformat(bin_parsers), ))

    parser_filepath = None
    is_bin_parser = False
    is_cross_parser = False
    for filepath in bin_parsers:
        if parser_name in filepath:
            logger.debug("parser: using %s" % (filepath, ))
            parser_filepath = filepath
            is_bin_parser = True
    if not parser_filepath:
        for filepath in cross_parsers:
            if parser_name in filepath:
                logger.debug("parser: using %s" % (filepath, ))
                parser_filepath = filepath
                is_cross_parser = True
    assert(os.path.isfile(parser_filepath)), "%s is not a good parser_filepath" % (parser_filepath, )
    assert(any([is_bin_parser, is_cross_parser])), "Parser is neither a binary nor a cross."
    assert(not all([is_bin_parser, is_cross_parser])), "Parser is both a binary and a cross."
    # ------------------------------------------------------------------------

    context = zmq.Context(1)

    # ------------------------------------------------------------------------
    #   Subscribing to the single masspinger instance to determine if
    #   the host is alive.
    # ------------------------------------------------------------------------
    masspinger_sub_socket = context.socket(zmq.SUB)
    masspinger_sub_socket.connect(masspinger_zeromq_binding)
    masspinger_sub_socket.setsockopt(zmq.SUBSCRIBE, host)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Subscribing to the ssh_tap output, which we'll pass to the parser.
    #   !!AI No, the parser already SUBSCRIBEs to this.
    # ------------------------------------------------------------------------
    #ssh_tap_sub_socket = context.socket(zmq.SUB)
    #ssh_tap_sub_socket.connect(ssh_tap_zeromq_binding)
    #ssh_tap_sub_socket.setsockopt(zmq.SUBSCRIBE, "")
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Requesting the services of a parser.
    #   !!AI No, the parser PUBLISHs its data.
    # ------------------------------------------------------------------------
    #parser_req_socket = context.socket(zmq.REQ)
    #parser_req_socket.connect(parser_zeromq_binding)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Publishing JSON for parsed log data.
    #   !!AI No, the parser publishes it by itself.
    # ------------------------------------------------------------------------
    #results_pub_socket = context.socket(zmq.PUB)
    #results_pub_socket.connect(results_zeromq_binding)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    # State for monitoring the liveliness of the host.
    # ------------------------------------------------------------------------
    host_alive = True
    last_host_response_time = time.time()
    last_host_response_time_threshold = 5
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    # State for executing ssh_tap
    # ------------------------------------------------------------------------
    logger.debug("ssh_tap location: %s" % (ssh_tap_filepath, ))
    ssh_tap_process = None
    ssh_tap_command = ssh_tap_template.substitute(executable = ssh_tap_filepath,
                                                 host = host,
                                                 command = command,
                                                 username = username,
                                                 password = password,
                                                 zeromq_bind = ssh_tap_zeromq_binding).strip()
    if verbose:
        ssh_tap_command += " --verbose"
    logger.debug("ssh_tap_command: %s" % (ssh_tap_command, ))
    ssh_tap_process_terminate_requested = False
    ssh_tap_process_terminate_time = None
    ssh_tap_process_terminate_threshold = 5
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    # State for the parser.
    # ------------------------------------------------------------------------
    logger.debug("parser location: %s" % (parser_filepath, ))
    parser_process = None
    if is_bin_parser:
        parser_executable = os.path.join(bin_directory, parser_name + bin_extension)
    else:
        parser_executable = python_executable + ' '
        parser_executable += os.path.join(cross_bin_directory, parser_name + ".py")
    parser_command = parser_template.substitute(executable = parser_executable,
                                                ssh_tap_zeromq_bind = ssh_tap_zeromq_binding,
                                                parser_zeromq_bind = parser_zeromq_binding).strip()
    if verbose:
        parser_command += " --verbose"
    logger.debug("parser command: %s" % (parser_command, ))
    # ------------------------------------------------------------------------

    poller = zmq.Poller()
    poller.register(masspinger_sub_socket, zmq.POLLIN)
    #poller.register(ssh_tap_sub_socket, zmq.POLLIN)
    poll_interval = 1000
    try:
        # Parser is always running, pop start here.
        if parser_process is None:
            logger.debug("Launching parser_process...")
            parser_process = start_process(parser_command)

        while 1:
            if ssh_tap_process is None and host_alive:
                logger.debug("Launching ssh_tap_process...")
                ssh_tap_process = start_process(ssh_tap_command)
            if ssh_tap_process and \
               (ssh_tap_process.poll() is None) and \
               (not host_alive):
                # Still running, but host is dead. Kill it.
                logger.debug("ssh_tap running, host is dead.")
                if not ssh_tap_process_terminate_requested:
                    logger.debug("terminate ssh_tap...")
                    terminate_process(ssh_tap_process, "ssh_tap_process")
                    ssh_tap_process_terminate_requested = True
                    ssh_tap_process_terminate_time = time.time()
                elif (time.time() - ssh_tap_process_terminate_time) > ssh_tap_process_terminate_threshold:
                    logger.debug("kill ssh_tap...")
                    terminate_process(ssh_tap_process, "ssh_tap_process", kill=True)
                    ssh_tap_process = None
                    ssh_tap_process_terminate_requested = False
                    ssh_tap_process_terminate_time = None
            elif ssh_tap_process and \
                 (ssh_tap_process.poll() is not None):
                # Not running any more.
                logger.debug("ssh_tap ended, return code: %s" % (ssh_tap_process.poll(), ))
                ssh_tap_process = None

            socks = dict(poller.poll(poll_interval))
            #logger.debug("tick")

            if socks.get(masspinger_sub_socket, None) == zmq.POLLIN:
                # Receive host liveliness.
                [hostname, contents] = masspinger_sub_socket.recv_multipart()
                host_alive = contents == "responsive"
                last_host_response_time = time.time()
                logger.debug(contents)
            elif (host_alive == False) and ((time.time() - last_host_response_time) > last_host_response_time_threshold):
                # If we haven't received an update about the host
                # within a certain amount of time assume masspinger
                # is dead and further assume the host is alive.
                logger.debug("Assuming masspinger is dead, and host is alive")

            #if socks.get(ssh_tap_sub_socket, None) == zmq.POLLIN:
            #    contents = ssh_tap_sub_socket.recv()
            #    logger.debug("ssh_tap_sub_read: %s" % (contents, ))

    except KeyboardInterrupt:
        logger.debug("CTRL-C")
    finally:
        terminate_process(ssh_tap_process, "ssh_tap_process", kill=True)
        terminate_process(parser_process, "parser_process", kill=True)
        logger.debug("finished.")

def start_process(command_line):
    logger = logging.getLogger("%s.start_process" % (APP_NAME, ))
    logger.debug("Starting: %s" % (command_line, ))
    if platform.system() == "Linux":
        proc = subprocess.Popen(command_line, shell=True)
    else:
        # To allow sending CTRL_C_EVENT signals to the process set
        # a Windows-only creation flag.
        proc = subprocess.Popen(command_line,
                                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP)
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
        if kill:
            logger.debug("...and kill")
            time.sleep(1)
            process_object.kill()
        return True
    except:
        logger.exception("unhandled exception while terminating %s." % (process_name))
        return False

if __name__ == "__main__":
    logger.debug("starting.")
    parser = argparse.ArgumentParser("Execution of SSH commands robust to network failure.")
    parser.add_argument("--masspinger",
                        dest="masspinger_zeromq_binding",
                        metavar="ZEROMQ_BINDING",
                        default=None,
                        help="ZeroMQ binding we SUBSCRIBE to for masspinger results.")
    parser.add_argument("--ssh_tap",
                        dest="ssh_tap_zeromq_binding",
                        metavar="ZEROMQ_BINDING",
                        required=True,
                        help="ZeroMQ binding we use for the ssh_tap instance.")
    parser.add_argument("--parser",
                        dest="parser_zeromq_binding",
                        metavar="ZEROMQ_BINDING",
                        required=True,
                        help="ZeroMQ binding we use to parse the logs.")
    parser.add_argument("--parser_name",
                        dest="parser_name",
                        metavar="PARSER_NAME",
                        required=True,
                        help="Name of the parser we'll look for to execute to parse ssh_tap output.")
    parser.add_argument("--results",
                        dest="results_zeromq_binding",
                        metavar="ZEROMQ_BINDING",
                        required=True,
                        help="ZeroMQ binding we PUBLISH our results to.")
    parser.add_argument("--host",
                        dest="host",
                        metavar="DNS_OR_IP",
                        required=True,
                        help="DNS hostname or IP address to SSH to.")
    parser.add_argument("--command",
                        dest="command",
                        metavar="COMMAND",
                        required=True,
                        help="Command to execute.")
    parser.add_argument("--username",
                        dest="username",
                        metavar="USERNAME",
                        default=None,
                        help="Username to SSH with.")
    parser.add_argument("--password",
                        dest="password",
                        metavar="PASSWORD",
                        default=None,
                        help="Password to SSH With.")
    parser.add_argument("--timeout",
                        dest="timeout",
                        metavar="TIMEOUT",
                        default=None,
                        help="Timeout. <= 0 is infinity.")
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

    main(masspinger_zeromq_binding = args.masspinger_zeromq_binding,
         ssh_tap_zeromq_binding = args.ssh_tap_zeromq_binding,
         parser_zeromq_binding = args.parser_zeromq_binding,
         parser_name = args.parser_name,
         results_zeromq_binding = args.results_zeromq_binding,
         host = args.host,
         command = args.command,
         username = args.username,
         password = args.password,
         timeout = args.timeout,
         verbose = args.verbose)

    logger.debug("finishing.")

