# ---------------------------------------------------------------------------
# Copyright (c) 2011 Asim Ihsan (asim dot ihsan at gmail dot com)
# Distributed under the MIT/X11 software license, see the accompanying
# file license.txt or http://www.opensource.org/licenses/mit-license.php.
# ---------------------------------------------------------------------------

import os
import sys
import zmq
import pprint
import datetime
import re
import json

import logging
logger = logging.getLogger("vm_messages_parser")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

class LogDatum(object):
    def __init__(self, string_input):
        self.string_input = string_input
        
    def get_dict_representation(self):
        """ Given a block of a full log event return a dict with the following
        required keys:
        -   year: integer
        -   month: integer
        -   day: integer
        -   hour: integer
        -   minute: integer
        -   second: integer
        -   contents: full block from the log.
        
        and the following optional keys:
        -   millisecond: integer
        
        Example lines:
        
        2012-Feb-25 19:36:44 testvm.2 green a a a a a a a a a a a a a
        2012-Feb-25 19:36:43 testvm.2 a a a a a a a a a a a a a i am a lion watch me roar
        
        - If the log outputs data in single lines contents will always be a single line.
        - If the log outputs data to multiple lines for a given datetime contents may
        be a line-delimited string.
        """
    
        return {"contents": self.string_input}
        
    def __str__(self):
        return str(self.get_dict_representation)

def validate_command(command):
    if "contents" not in command:
        return False
    return True

def split_contents_and_return_excess(contents):
    """ Given a block of text in contents split it into lines, and
    return a two-element tuple (elem1, elem2).
    -   elem1: list of strings for lines in the contents. If there
        are no full lines return an empty list.
    -   elem2: string of the excess, i.e. the last line.
        
    Examples below:

    contents = ""
    return ([], "")
    
    contents = "12345"
    return ([], "")
    
    contents = "12345\r\n"
    return (["12345", ""])
    
    contents = "12345\n"
    return (["12345", ""])    
    
    contents = "12345\n123456\n123457"    
    return (["12345", "123456"], "1234567")
    
    """
    
    if len(contents) == 0:        
        return_value = ([], "")    
    else:
        # After splitting lines we need to restore line breaks
        lines = contents.splitlines()        
        for i, line in enumerate(lines[:-1]):
            lines[i] = ''.join(lines[i], '\n')
            
        if len(lines) == 1:            
            return_value = ([], lines[0])
        else:        
            return_value = (lines[:-1], lines[-1])    
    logger.debug("returning : %s" % (return_value, ))
    return return_value

if __name__ == "__main__":
    logger.info("starting")
    
    PROTOCOL = "tcp"
    HOSTNAME = "127.0.0.1"
    PORTS = [2000]
    FILTER = ""
    
    connections = ["%s://%s:%s" % (PROTOCOL, HOSTNAME, port) for port in PORTS]
    logger.debug("Collecting updates from: %s" % (pprint.pformat(connections), ))
    
    context = zmq.Context(1)
    socket = context.socket(zmq.SUB)
    map(socket.connect, connections)
    socket.setsockopt(zmq.SUBSCRIBE, FILTER)
    
    trailing_excess = ""    
    full_lines = []
    while 1:
        incoming_string = socket.recv()
        logger.debug("Update: '%s'" % (incoming_string, ))
        try:
            incoming_object = json.loads(incoming_string)
        except:
            logger.exception("Can't decode command:\n%s" % (incoming_string, ))
            continue        
        if not validate_command(incoming_object):
            logger.error("Not a valid command: \n%s" % (incoming_object))
            continue
        trailing_excess = ''.join([trailing_excess, incoming_object["contents"]])     
        (new_full_lines, trailing_excess) = split_contents_and_return_excess(trailing_excess)        
        full_lines.extend(new_full_lines)
        logger.debug("full_lines:\n%s" % (full_lines, ))
        logger.debug("trailing_excess:\n%s" % (trailing_excess, ))
        
        