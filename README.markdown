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

-   On file rotation if we use a version of tail that does not support the '--follow=name' flag we will fail to pick up the new log contents. Fix is to start a total of three libssh2 sessions for a given tap that requires tailing
    -   The first is the regular tail.
    -   The second is an empty session, doing nothing and twiddling its thumbs.
    -   The third is an infinite while [[ 1 ]] sleep 1 that uses 'ls -i' to get the inode number of the file. If it changes:
        -   Kill the first session.
        -   Use the second session to tail the file again.
        -   Start a new session to take the place of backup.
    Of course you could avoid this by using a real version of tail, but BusyBox doesn't have one.

TODO
----

-   Write a Python framework like supervisord for parsing config and launching stuff.
    -   Launching-wise, we always want one masspinger instance, and N robust_ssh_tap instances.
    -   Write a cheeky sleep(1) script that parses config and does this.
-   Test the framework on the local install, make sure it works.

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
