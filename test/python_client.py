# ---------------------------------------------------------------------------
# Copyright (c) 2011 Asim Ihsan (asim dot ihsan at gmail dot com)
# Distributed under the MIT/X11 software license, see the accompanying
# file license.txt or http://www.opensource.org/licenses/mit-license.php.
# ---------------------------------------------------------------------------

import os
import sys
import zmq
import pprint

import logging
logger = logging.getLogger("python_client")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

if __name__ == "__main__":
    logger.info("starting")

    binding = "tcp://127.0.0.1:%s" % (sys.argv[1], )
    logger.debug("Collecting updates from: %s" % (binding, ))

    context = zmq.Context(1)
    socket = context.socket(zmq.SUB)
    socket.connect(binding)
    socket.setsockopt(zmq.SUBSCRIBE, "")

    while 1:
        incoming = socket.recv()
        logger.debug("Update: '%s'" % (incoming, ))

