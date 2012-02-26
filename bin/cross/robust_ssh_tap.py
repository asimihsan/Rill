#!/usr/bin/env python2.7

# ---------------------------------------------------------------------------
# Copyright (c) 2011 Asim Ihsan (asim dot ihsan at gmail dot com)
# Distributed under the MIT/X11 software license, see the accompanying
# file license.txt or http://www.opensource.org/licenses/mit-license.php.
# ---------------------------------------------------------------------------

import os
import sys
import argparse
import subprocess
import zmq
import time

APP_NAME = "robust_ssh_tap"
import logging
logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

def main(masspinger_zeromq_binding,
         parser_zeromq_binding,
         results_zeromq_binding,
         host,
         command,
         username,
         password,
         timeout):
    logger = logging.getLogger("%s.main" % (APP_NAME, ))
    logger.debug("entry.")
    logger.debug("masspinger_zeromq_binding: %s" % (masspinger_zeromq_binding, ))
    logger.debug("parser_zeromq_binding: %s" % (parser_zeromq_binding, ))
    logger.debug("results_zeromq_binding: %s" % (results_zeromq_binding, ))
    logger.debug("host: %s" % (host, ))
    logger.debug("command: %s" % (command, ))
    logger.debug("username: %s" % (username, ))
    logger.debug("timeout: %s" % (timeout, ))

    context = zmq.Context(1)

    # ------------------------------------------------------------------------
    #   Subscribing to the raw ssh_tap from a server.
    # ------------------------------------------------------------------------
    subscription_binding = masspinger_zeromq_binding
    subscription_socket = context.socket(zmq.SUB)
    subscription_socket.connect(subscription_binding)
    subscription_socket.setsockopt(zmq.SUBSCRIBE, host)
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    #   Publishing JSON for parsed log data.
    # ------------------------------------------------------------------------
    #publish_binding = "tcp://127.0.0.1:3000"
    #publish_socket = context.socket(zmq.PUB)
    #publish_socket.connect(publish_binding)
    # ------------------------------------------------------------------------

    poller = zmq.Poller()
    poller.register(subscription_socket, zmq.POLLIN)
    poll_interval = 1000

    try:

        while 1:
            # Receive host liveliness.
            socks = dict(poller.poll(poll_interval))
            if subscription_socket in socks and \
               socks[subscription_socket] == zmq.POLLIN:

                args = subscription_socket.recv_multipart(zmq.NOBLOCK)
                logger.debug(args)

            logger.debug("tick")

    except KeyboardInterrupt:
        logger.debug("CTRL-C")
    finally:
        logger.debug("finished.")

if __name__ == "__main__":
    logger.debug("starting.")
    parser = argparse.ArgumentParser("Execution of SSH commands robust to network failure.")
    parser.add_argument("--masspinger",
                        dest="masspinger_zeromq_binding",
                        metavar="ZEROMQ_BINDING",
                        default=None,
                        help="ZeroMQ binding we SUBSCRIBE to for masspinger results.")
    parser.add_argument("--parser",
                        dest="parser_zeromq_binding",
                        metavar="ZEROMQ_BINDING",
                        required=True,
                        help="ZeroMQ binding we use to parse the logs.")
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
         parser_zeromq_binding = args.parser_zeromq_binding,
         results_zeromq_binding = args.results_zeromq_binding,
         host = args.host,
         command = args.command,
         username = args.username,
         password = args.password,
         timeout = args.timeout)

    logger.debug("finishing.")

