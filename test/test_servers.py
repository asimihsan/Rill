import os
import sys
import datetime
from string import Template
import random
import paramiko
import time
import select

class SshConnection(object):
    def __init__(self, address, username, password):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(address,
                                username=username,
                                password=password)

    def close(self):
        self.ssh_client.close()

    def invoke_shell(self):
        return self.ssh_client.invoke_shell()

class SshChannel(object):
    def __init__(self, client):
        self.client = client
        self.initialize()

    def initialize(self):
        self.channel = self.client.invoke_shell()

    def send_command(self, command):
        self.channel.sendall(command)

    def close(self):
        self.channel.close()

    def get_channel_object(self):
        return self.channel

    def recv_ready(self):
        return self.channel.recv_ready()

    def recv(self, size):
        return self.channel.recv(size)

    def send_ready(self):
        return self.channel.send_ready()

SERVERS = [ \
            "testvm.1",
            "testvm.2"
             ]
SERVER_LOG_PATH = "/home/ubuntu/test.log"
DATETIME_OUTPUT_FORMAT = "%Y-%b-%d %H:%M:%S"
RANDOM_WORDS = [
                "blue",
                "green",
                "yellow brown",
                "orange blue",
                "i am a lion watch me roar",
                "FIERCE UPPER CASE",
                "a a a a a a a a a a a a a",
                "aa aa aa aa aa"
                ]
LINE_TEMPLATE = Template("${datetime} ${server_id} ${contents}")
STARTUP_COMMAND = Template("rm -f ${filepath}\n")

LOG_COMMAND = Template("echo \"${contents}\" >> ${filepath}\n")
LOG_COMMAND_TRUNCATED_NO_LINE_BREAK = Template("echo -n \"${contents}\" >> ${filepath}\n")

def flush_channel_output(channels):
    channel_objects = [channel.get_channel_object() for channel in channels]
    rl, wl, xl = select.select(channel_objects, [], [], 0.1)
    if len(rl) > 0:
        for channel in channels:
            channel_object = channel.get_channel_object()
            if channel_object in rl and channel_object.recv_ready():
                output = channel_object.recv(1024)

if __name__ == "__main__":
    random_seed = "c7d73a76-4e1a-4df4-ae9f-18feb340d753"
    random.seed(random_seed)

    print "Connecting..."
    username = "ubuntu"
    password = "password"
    connections = [SshConnection(address, username, password)
                   for address in SERVERS]
    channels = [SshChannel(connection) for connection in connections]
    for channel in channels:
        channel.initialize()
    flush_channel_output(channels)
    for channel in channels:
        command = STARTUP_COMMAND.substitute(filepath=SERVER_LOG_PATH)
        channel.send_command(command)
    print "Finished connecting"
    try:
        servers_and_channels = zip(SERVERS, channels)
        while 1:
            flush_channel_output(channels)
            if random.randint(1, 2) != 2:
                # sometimes output lines with duplicate timestamps
                time.sleep(1)
            for (server, channel) in servers_and_channels:
                now = datetime.datetime.now()
                now_string = now.strftime(DATETIME_OUTPUT_FORMAT)
                contents = ' '.join([random.choice(RANDOM_WORDS) for i in xrange(2)])
                line = LINE_TEMPLATE.substitute(datetime=now_string,
                                                server_id=server,
                                                contents=contents)
                if random.randint(1, 2) != 2:
                    # sometimes duplicate and fragment the line.
                    line = '\r\n'.join([line, line])
                    index = random.randint(1, len(line)-1)
                    part1 = line[:index]
                    part2 = line[index:]
                    command = LOG_COMMAND_TRUNCATED_NO_LINE_BREAK.substitute(contents=part1,
                                                                             filepath=SERVER_LOG_PATH)
                    channel.send_command(command)
                    if random.randint(1, 2) != 2:
                        # sometimes delay between parts of the line
                        time.sleep(1)
                    command = LOG_COMMAND.substitute(contents=part2,
                                                     filepath=SERVER_LOG_PATH)
                    channel.send_command(command)
                else:
                    command = LOG_COMMAND.substitute(contents=line,
                                                     filepath=SERVER_LOG_PATH)
                    channel.send_command(command)
    except KeyboardInterrupt:
        print "CTRL-C"
    finally:
        print "Finishing..."
        for channel in channels:
            channel.close()
        for connection in connections:
            connection.close()
        print "Finished."


