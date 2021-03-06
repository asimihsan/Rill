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
    from constants import *
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
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   If we're performing a tail that does not have "follow=name" in it
    #   then we're going to fail to follow rotated files. Launch a
    #   separate instance to track the inode of the file being tailed,
    #   and restart everything if it rolls.
    # ------------------------------------------------------------------------
    tail_query_inode_process = None
    tail_query_inode_sub_socket = None
    last_inode = None
    is_tail_query_inode_required = command.startswith("tail") and "follow=name" not in command
    if is_tail_query_inode_required:
        logger.debug("perform tail query inode monitoring.")
        log_filepath = command.split()[-1].strip("'\r\n")
        logger.debug("log filepath: '%s'" % (log_filepath, ))
        tail_query_inode_subcmd = tail_query_inode_template.substitute(log_filepath = log_filepath).strip()
        current_ssh_tap_zeromq_binding_port = int(ssh_tap_zeromq_binding.split(":")[-1])
        logger.debug("current_ssh_tap_zeromq_binding_port: %s" % (current_ssh_tap_zeromq_binding_port, ))
        tail_query_inode_zeromq_binding = "tcp://127.0.0.1:%s" % (current_ssh_tap_zeromq_binding_port + 1, )
        tail_query_inode_command = ssh_tap_template.substitute(executable = ssh_tap_filepath,
                                                               host = host,
                                                               command = tail_query_inode_subcmd,
                                                               username = username,
                                                               password = password,
                                                               zeromq_bind = tail_query_inode_zeromq_binding).strip()
        if verbose:
            tail_query_inode_command += " --verbose"
        logger.debug("tail_query_inode_command: %s" % (tail_query_inode_command, ))

        tail_query_inode_sub_socket = context.socket(zmq.SUB)
        tail_query_inode_sub_socket.connect(tail_query_inode_zeromq_binding)
        tail_query_inode_sub_socket.setsockopt(zmq.SUBSCRIBE, "")
    # ------------------------------------------------------------------------


    # ------------------------------------------------------------------------
    # State for the parser. Combination of a parser and a
    # parser_tap_to_database.
    # ------------------------------------------------------------------------
    logger.debug("parser location: %s" % (parser_filepath, ))
    parser_process = None
    box_name = "%s_%s" % (host, parser_name)
    if is_bin_parser:
        parser_executable = os.path.join(bin_directory, parser_name + bin_extension)
    else:
        parser_executable = python_executable + ' '
        parser_executable += os.path.join(cross_bin_directory, parser_name + ".py")
    parser_command = parser_template.substitute(executable = parser_executable,
                                                ssh_tap_zeromq_bind = ssh_tap_zeromq_binding,
                                                parser_zeromq_bind = parser_zeromq_binding,
                                                box_name = box_name).strip()
    if verbose:
        parser_command += " --verbose"
    logger.debug("parser command: %s" % (parser_command, ))

    parser_tap_to_database_process = None
    collection = "%s_%s" % (host, parser_name)
    parser_tap_to_database_executable = python_executable + ' ' + parser_tap_to_database_filepath
    parser_tap_to_database_command = parser_tap_to_database_template.substitute(executable = parser_tap_to_database_executable,
                                                                                results_zeromq_bind = parser_zeromq_binding,
                                                                                collection = collection).strip()
    if verbose:
        parser_tap_to_database_command += " --verbose"
    logger.debug("parser_tap_to_database command: %s" % (parser_tap_to_database_command, ))
    # ------------------------------------------------------------------------

    poller = zmq.Poller()
    poller.register(masspinger_sub_socket, zmq.POLLIN)
    if is_tail_query_inode_required:
        poller.register(tail_query_inode_sub_socket, zmq.POLLIN)
    poll_interval = 1000
    try:
        while 1:
            if host_alive:
                if ssh_tap_process is None:
                    logger.debug("ssh_tap_process not running, so restart it.")
                    ssh_tap_process = start_process(ssh_tap_command, verbose)
                if is_tail_query_inode_required and tail_query_inode_process is None:
                    logger.debug("tail_query_inode_process not running, so restart it.")
                    tail_query_inode_process = start_process(tail_query_inode_command, verbose)
                if parser_process is None:
                    logger.debug("parser_process not running, so restart it.")
                    parser_process = start_process(parser_command, verbose)
                if parser_tap_to_database_process is None:
                    logger.debug("parser_tap_to_database_process not running, so restart it.")
                    parser_tap_to_database_process = start_process(parser_tap_to_database_command, verbose)
            else:
                if ssh_tap_process and (ssh_tap_process.poll() is None):
                    logger.debug("ssh_tap_process running but host dead, so kill it.")
                    terminate_process(ssh_tap_process, "ssh_tap_process")
                if is_tail_query_inode_required and tail_query_inode_process and (tail_query_inode_process.poll() is None):
                    logger.debug("tail_query_inode_process running but host dead, so kill it.")
                    terminate_process(tail_query_inode_process, "tail_query_inode_process")
                #if parser_process and (parser_process.poll() is None):
                #    logger.debug("parser running but host dead, so kill it.")
                #    terminate_process(parser_process, "parser_process")
                #if parser_tap_to_database_process and (parser_tap_to_database_process.poll() is None):
                #    logger.debug("parser_tap_to_database running but host dead, so kill it.")
                #    terminate_process(parser_tap_to_database_process, "parser_tap_to_database_process")

            if ssh_tap_process and (ssh_tap_process.poll() is not None):
                logger.debug("ssh_tap_process ended, return code %s." % (ssh_tap_process.poll(), ))
                ssh_tap_process = None
            if is_tail_query_inode_required and tail_query_inode_process and (tail_query_inode_process.poll() is not None):
                logger.debug("tail_query_inode_process ended, return code %s." % (tail_query_inode_process.poll(), ))
                tail_query_inode_process = None
            if parser_process and (parser_process.poll() is not None):
                logger.debug("parser_process ended, return code %s." % (parser_process.poll(), ))
                parser_process = None
            if parser_tap_to_database_process and (parser_tap_to_database_process.poll() is not None):
                logger.debug("parser_tap_to_database_process ended, return code %s." % (parser_tap_to_database_process.poll(), ))
                parser_tap_to_database_process = None

            socks = dict(poller.poll(poll_interval))
            if socks.get(masspinger_sub_socket, None) == zmq.POLLIN:
                # Receive host liveliness.
                [hostname, contents] = masspinger_sub_socket.recv_multipart()
                host_alive = contents == "responsive"
                last_host_response_time = time.time()
                logger.debug(contents)
            if (host_alive == False) and ((time.time() - last_host_response_time) > last_host_response_time_threshold):
                # If we haven't received an update about the host
                # within a certain amount of time assume masspinger
                # is dead and further assume the host is alive.
                logger.debug("Assuming masspinger is dead, and host is alive")
                host_alive = True
            if is_tail_query_inode_required and socks.get(tail_query_inode_sub_socket, None) == zmq.POLLIN:
                contents = tail_query_inode_sub_socket.recv()
                try:
                    contents_decoded = json.loads(contents)
                except:
                    logger.error("couldn't decode inode socket contents: %s" % (contents, ))
                else:
                    if contents_decoded["contents"].strip().isdigit():
                        old_last_inode = last_inode
                        last_inode = contents_decoded["contents"].strip()
                        logger.debug("inode updated from %s to %s" % (old_last_inode, last_inode))
                        if all(elem is not None for elem in [last_inode, old_last_inode]) and (last_inode != old_last_inode):
                            logger.debug("the file we're tailing has rotated.")
                            terminate_process(ssh_tap_process, "ssh_tap_process")
    except KeyboardInterrupt:
        logger.debug("CTRL-C")
    finally:
        terminate_process(ssh_tap_process, "ssh_tap_process", kill=True)
        terminate_process(parser_process, "parser_process", kill=True)
        terminate_process(parser_tap_to_database_process, "parser_tap_to_database_process", kill=True)
        if is_tail_query_inode_required:
            terminate_process(tail_query_inode_process, "tail_query_inode_process", kill=True)
        logger.debug("finished.")

def start_process(command_line, verbose = False):
    logger = logging.getLogger("%s.start_process" % (APP_NAME, ))
    logger.debug("Starting: command_line: %s, verbose: %s" % (command_line, verbose))
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

