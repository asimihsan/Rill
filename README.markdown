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

TODO
----

-   Write a Python mockup of a combination of ssh_tap / masspinger / XXX that makes this output durable to network loss, just for the real-time stream (not all log data).
    -   Call it "robust_ssh_tap"    
    -   Args:
        -   m:  What ZeroMQ binding should we get masspinger results from? If not available, assume the host is
available, i.e. non-robust. We SUBSCRIBE to it with a filter for our hosts.
        -   p:  What ZeroMQ binding should we use to parse the logs? This is a REQ socket, i.e. request/response.
        -   b:  What ZeroMQ binding to send out our parsed results? This is a PUBLISH socket.
        -   h:  Host.
        -   c:  Command.
        -   u:  Username.
        -   p:  Password.
        -   t:  Timeout.
        -   v:  Verbose.

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