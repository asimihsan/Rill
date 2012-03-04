Rill
====

Introduction
------------

Rill will monitor many file-based log files on many systems over SSH. Its primary focus is on a "light touch": target systems are only required to offer SSH access. Such access need not be based on public-keys because this would imply we are able to modify the server's authorized_keys file. In general no software or configuration is required on the target boxes.  Moreover, Rill's design emphasises decomposition and interfaces over network sockets so that sub-components are easily grokable and reusable in other projects.

Functional requirements:

-   Monitor file-based log files on servers.
-   Offer historical text-based search over the files.
-   Offer real-time access to log file contents over a network socket.

Non-functional requirements:

-   Be robust to network failures. Historical log data is 1:1 with server log data in the long run (eventually consistent and always available in the face of partitioning).

BUGS
----

-   On file rotation if we use a version of tail that does not support the '--follow=name' flag (Solaris, BusyBox Linux) we will fail to pick up the new log contents. Fix is to start a total of three libssh2 sessions for a given tap that requires tailing
    -   The first is the regular tail.
    -   The second is an empty session, doing nothing and twiddling its thumbs.
    -   The third is an infinite while [[ 1 ]] sleep 1 that uses 'ls -i' to get the inode number of the file. If it changes:
        -   Kill the first session.
        -   Use the second session to tail the file again.
        -   Start a new session to take the place of backup.
    Of course you could avoid this by using a real version of tail, but BusyBox doesn't have one.

-   parsers stop reading in output from ssh_tap via SUBSCRIBE after a while. Why? ssh_tap says it's PUBLISHing it. Does this happen when ssh_tap restarts? Does ZeroMQ SUBSCRIBE just stop working? It's a blocking recv() call...maybe we should restart the parser instance when ssh_tap is restarted?

-   If an ssh_tap is outputting so much data that a parser subscriber cannot keep up, the ZeroMQ SUBSCRIBE binding, by default, keeps all pending messages in memory. This leads to memory increasing indefinitely. Want to adjust the SUBSCRIBE binding to have a finite high water mark and either keep them in swap memory or discard messages.

TODO
----

- ssh_tap as it stands is alright. I want to extend it to support the following:
    -   Support multiple, simultaneous command execution. It will open SSH channels within the current session, get to a pexpect state, and then run the commands on them.
    -   Real-time signalling. I want to be able to SUBSCRIBE to SSH data from a box, regex on it, then send new data based on it. This is exactly what ssh_tap does on it's own, but I want external clients to get raw data fromm ssh_tap and do this on their own.
    -   Define two types of ZeroMQ sockets - data and signalling.
        -   The data sockets are where we PUBLISH results. Do we want to have one data socket and publish results based on a text-prefix, and expect subscribers to filter? Or do we want 1:1 ZeroMQ sockets for each session we have open? I'm leaning towards the latter, as I don't want to spam quiet subscribers with redundant noisy traffic. So let's run with many ZeroMQ PUBLISH sockets.
        -   The signalling sockets XREP sockets where XREP clients can execute the following via JSON:
            -   all messages which are requests from clients must contain the following fields:
                -   unique_id: a string that is a globally unique identifier for the particular message. clients should use something like Python's uuid.uuidv4().
                -   client_id: a string that is a unique identifier for the client within the scope of the system. clients should generate a UUID on startup and assume that the ID is globally unique.
                -   datetime:  a ISO 8601 compliant string corresponding to the UTC time at which the request was sent. Corresponds to calling the following in Python: datetime.datetime.now().isoformat() + 'Z'. example: '2002-12-25T00:00:00.000Z' (there must be three digits for the millisecond precision).
            -   all messages which are replies to a given request must contain the following fields:
                -   unique_id: the same string that was on the incoming request must be returned on the response.
                -   client_id: the same string that was on the incoming request for the client_id must be returned on the response.
                -   datetime: ISO 8601 datetime for when the server sent the response.
                -   status: this field is mandatory. 'ok' if command was succesful, 'failed' if not.
                -   failure_reason: if status is 'ok' this field may be ommitted. if status is 'failed' this field is mandatory. is a human-readable reason for why the particular request failed.
            -   global failure modes to consider:
                -   REP/REQ sockets are durable. if a request arrives that is very old, do we want to discard it? assume everyone is NTP-ed up.                
            -   create_session. Create a new session to the server that support pexpect-behaviour.
                -   the request contains no fields besides the globally mandatory ones.
                -   fields on response:                    
                    -   session_id: a globally unique identifier that corresponds to the session on the SSH server, that can be referenced in subsequent calls.
                    -   publish_zeromq_bind: a string for the PUBLISH zeromq binding that the client can SUBSCRIBE to in order to receive data sent from the session. in theory the client has already missed out some data because they'll be SUBSCRIBE-ing a bit late, but assume this initial data isn't interesting (e.g. bash banner). I don't want to have to cache / send this.
                -   failure modes to consider:
                    -   how many simultaneous sessions do you really want open? Maybe cap it at N, and reject subsequent create requests.
            -   delete_session. Immediately delete the session, do not make any special attempt to recover more output from the session.
                -   fields on request:
                    -   session_id: the ID for the session.
                -   fields on response are nothing besides the globally mandatory ones.
            -   send_data_to_session. Send a block of data to the session. Doesn't necesarily have to be terminated by a line break, and ssh_tap will not append a line break for you.
                -   fields on request:
                    -   session_id: what session to push data into.
                    -   contents: what to push into the session.
                -   fields on response:
                    -   bytes written: the return code from libssh2_channel_write(), just punt it back. if this isn't equal to the command length put this in the failure reason.
                -   failure modes to consider:
                    -   does the session exist? if not return a failure.
            -   get_session_info: get information on running sessions right now.
                -   fields on request:
                    -   session_id: optional. if specified try to recover information about a particular session. if this is ommitted we will return information about all running sessions.
                -   fields on response:
                    -   a list of sessions. could be an empty list, else for each session return:
                        -   session_id.
                        -   client_id: for the requester who created the session.
                        -   datetime: for when the session was opened.
                        -   bytes written: total number of bytes written into the session.
                        -   bytes read: total number of bytes read from the session.
                
    -   On startup start a pool of e.g. 5 sessions. Get these all ready at the pexpect prompts.
    -   Do not reuse sessions. When a session gets delete really delete it, don't put it back into a pool of free sessions. This creates exciting race conditions, e.g. hammering ssh_tap with a catastrophic mix of create and delete commands and seeing what it does.
    -   If ssh_tap thinks it's gotten into a pickle just assert. We assume a robust wrapper, i.e. robust_ssh_tap, is sitting outside ssh_tap ready to relaunch it.


TODO (done)
-----------

-   Create mock servers. Write two cheeky Python scripts that pipe output into test log files on two VirtualBox instances.
-   Write the highest-possible level config file an operator would use to configure Rill to monitor these two VirtualBox instances' log files.
    -   What boxes are you monitoring?
    -   What files do you want to monitor?    -   
    -   What parser will handle this log file? You need a separate process that talks over ZeroMQ to parse this data. This parse handles putting log data into the durable store.
    -   Durable store information.
-   Add static build of log4cxx.
-   Add logging to ssh_tap.
-   Add masspinger to rill.
-   Confirm ssh_tap works for the two log files. We need to output full lines, one ZeroMQ message per line, no parsing of lines.
-   Write a Python mockup of a parser that hooks into the log files and outputs parsed data, i.e. a JSON pair (datetime, contents).
-   Write a Python mockup of a combination of ssh_tap / masspinger / XXX that makes this output durable to network loss, just for the real-time stream (not all log data).
    -   Call it "robust_ssh_tap"    
    -   Args:
        -   m:  What ZeroMQ binding should we get masspinger results from? If not available, assume the host is
available, i.e. non-robust. We SUBSCRIBE to it with a filter for our hosts.
        -   p:  What ZeroMQ binding should we use to parse the logs? This is a REQ socket, i.e. request/response.
        -   b:  What ZeroMQ binding to send out our parsed results? This is a PUBLISH socket.
        -   s:  What ZeroMQ binding to use for the ssh_tap instance? We'll grab this.
        -   h:  Host.
        -   c:  Command.
        -   u:  Username.
        -   p:  Password.
        -   t:  Timeout.
        -   v:  Verbose.
-   Write a Python framework like supervisord for parsing config and launching stuff.
    -   Launching-wise, we always want one masspinger instance, and N robust_ssh_tap instances.
    -   Write a cheeky sleep(1) script that parses config and does this.
-   Test the framework on the local install, make sure it works.
