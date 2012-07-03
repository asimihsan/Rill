#!/usr/bin/env python2.7

from __future__ import with_statement

import os
import sys
import paramiko
import pprint
import subprocess
import socket
from string import Template
import multiprocessing
import time
import requests
import psutil

# -----------------------------------------------------------------------------
#   Constants.
# -----------------------------------------------------------------------------
APP_NAME = "monitor_and_recover_mongo"
LOG_FILENAME = "/var/log/rill/monitor_and_recover_mongo.log"
DEFAULT_USERNAME = "root"
DEFAULT_PASSWORD = "mng1"
BOX_HOSTNAMES = ["magpie", "rabbit", "rat"]
REPL_SET_TEMPL = Template("http://${hostname}:28017/replSetGetStatus")
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
#   Logging
# -----------------------------------------------------------------------------
import logging
import logging.handlers
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)
if not os.path.isdir(os.path.split(LOG_FILENAME)[0]):
    os.makedirs(os.path.split(LOG_FILENAME)[0])
ch2 = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=1024*1024*10, backupCount=10)
ch2.setFormatter(formatter)
ch2.setLevel(logging.DEBUG)
logger.addHandler(ch2)
logger = logging.getLogger(APP_NAME)
# -----------------------------------------------------------------------------

def is_box_available(host, username, password, timeout=5):
    return_code = True
    ssh = paramiko.SSHClient()
    try:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=username, password=password, timeout=timeout)
    except socket.timeout:
        return_code = False
    finally:
        ssh.close()
    return return_code

def execute_command(host, username, password, command, timeout=20):
    logger = logging.getLogger("%s.execute_command.%s" % (APP_NAME, host))
    logger.info("entry. command: %s" % (command, ))
    (parent_conn, child_conn) = multiprocessing.Pipe()
    p = multiprocessing.Process(target = _execute_command,
                                args = (host, username, password, command, timeout, child_conn))
    time_start = time.time()
    p.daemon = True
    p.start()
    while p.is_alive() and ((time.time() - time_start) <= timeout):
        time.sleep(0.5)
    if p.is_alive():
        logger.error("command is still running, taking too long.")
        parent_conn.close()
        child_conn.close()
        p.terminate()
        return None
    return_value = parent_conn.recv()
    logger.debug("command returns: %s" % (return_value, ))
    parent_conn.close()
    child_conn.close()
    p.terminate()
    return return_value

def _execute_command(host, username, password, command, timeout, conn):
    logger = logging.getLogger("%s._execute_command.%s" % (APP_NAME, host))
    ssh = paramiko.SSHClient()
    try:
        try:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, username=username, password=password, timeout=timeout)
        except socket.timeout:
            logger.exception("socket.timeout on connection to box: %s" % (host, ))
            return_value = None
        try:
            logger.info("executing command '%s'..." % (command, ))
            (stdin, stdout, stderr) = ssh.exec_command(command)
            stdout.channel.settimeout(5.0)
            logger.info("receiving exit status...")
            rc = stdout.channel.recv_exit_status()
            logger.info("exit status: %s" % (rc, ))
            stdout_value = ""
            while stdout.channel.recv_ready():
                chunk = stdout.channel.recv(1024)
                if len(chunk) == 0:
                    break
                stdout_value += chunk
            return_value = stdout_value
        except socket.timeout:
            logger.exception("Box: %s. Timeout on executing command: %s" % (host, command))
            return_value = None
        except paramiko.SSHException:
            logger.exception("Box: %s. Failed to execute command: %s" % (host, command))
            return_value = None
    finally:
        ssh.close()
    conn.send(return_value)
    conn.close()

def set_local_file_contents(filepath, file_contents):
    assert(os.path.isfile(filepath))
    with open(filepath, "w") as f:
        f.write(file_contents)

def get_local_file_contents(filepath):
    assert(os.path.isfile(filepath))
    with open(filepath) as f:
        return f.read().strip()

def get_remote_file_contents(host, username, password, filepath, timeout=10):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=timeout)
    sftp = ssh.open_sftp()
    print "Filepath: %s" % filepath
    f = sftp.open(filepath, "r")
    output = f.read().strip()
    f.close()
    sftp.close()
    ssh.close()
    return output

def set_remote_file_contents(host, username, password, filepath, file_contents, timeout=10):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=timeout)
    sftp = ssh.open_sftp()
    f = sftp.open(filepath, "w")
    f.write(file_contents)
    f.close()
    sftp.close()
    ssh.close()

def get_hostname_and_ip(hostname=None, ip_address=None):
    assert(any(arg is not None for arg in [hostname, ip_address]))
    logger.info("get_hostname_and_ip entry.hostname = %s ip address = %s" % (hostname,ip_address))
    if hostname is not None:
        ip_address = [elem[4] for elem in socket.getaddrinfo(hostname, 22)][0][0]
    else:
        assert(ip_address is not None)
        hostname = socket.gethostbyaddr(ip_address)[0].split(".")[0]
    return (hostname, ip_address)

class RemoteBox(object):
    def __init__(self, username, password, hostname=None, ip_address=None):
        self.username = username
        self.password = password

        self.hostname = hostname
        self.ip_address = ip_address
        assert(any(elem is not None for elem in [hostname, ip_address]))
        (self.hostname, self.ip_address) = get_hostname_and_ip(self.hostname, self.ip_address)

    def __str__(self):
        output = "Hostname: %s, IP Address: %s, Username: %s, Password: %s" % (self.hostname, self.ip_address, self.username, self.password)
        return output

    def __repr__(self):
        return str(self)

if __name__ == "__main__":
    logger.info("starting")

    # ------------------------------------------------------------------------
    #   Do not use this command if execute_db_maintenance is also running.
    # ------------------------------------------------------------------------
    processes = [psutil.Process(pid) for pid in psutil.get_pid_list()]
    if any("execute_db_maintenance" in " ".join(process.cmdline) for process in processes):
        logger.error("Will not run at the same time as execute_db_maintenance.")
        sys.exit(1)
    # ------------------------------------------------------------------------

    BOXES = [RemoteBox(username = DEFAULT_USERNAME,
                       password = DEFAULT_PASSWORD,
                       hostname = hostname)
             for hostname in BOX_HOSTNAMES]
    logger.info("boxes: \n%s" % (pprint.pformat(BOXES), ))
    for box in BOXES:
        # --------------------------------------------------------------------
        #   Check if the box is up.
        # --------------------------------------------------------------------
        logger.info("Checking box %s for availability..." % (box, ))
        if not is_box_available(box.hostname, box.username, box.password):
            logger.warning("box is not available via SSH. skipping.")
            continue
        # --------------------------------------------------------------------

        # --------------------------------------------------------------------
        #   Make sure the replicate set admin command doesn't hang
        #   on execution. If it does then reset its DB.
        # --------------------------------------------------------------------
        rv = execute_command(box.hostname, box.username, box.password,
                             "mongo --quiet admin --eval 'printjson(rs.status())'")
        if rv is None:
            logger.warning("box %s is not responding to a replica set admin command." % (box, ))
            rv = execute_command(box.hostname, box.username, box.password,
                                 "bash -c 'pkill -9 mongod; sleep 5; rm -rf /var/lib/mongo/*; service mongod start' 2>&1 >/dev/null &")
            logger.info("rv: %s" % (rv, ))
        # --------------------------------------------------------------------

        # --------------------------------------------------------------------
        #   Clean up old logs.
        # --------------------------------------------------------------------
        rv = execute_command(box.hostname, box.username, box.password,
                             "find /var/log/mongo/* -mtime +7 -exec rm {} \;")
        # --------------------------------------------------------------------
    logger.info("finishing.")

