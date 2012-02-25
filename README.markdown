Rill
====

Introduction
------------

Rill will monitor many file-based log files on many systems over SSH. Its primary focus is on a "light touch": target systems are only required to offer SSH access. Such accees need not be based on public-keys and no software or configuration is required on the target boxes.  Moreover, Rill's design emphasises decomposition and interfaces over network sockets so that sub-components are easily grokable and reusable in other projects.

Functional requirements:
-   Monitor file-based log files on servers.
-   Offer historical text-based search over the files.

Non-functional requirements:
-   Be robust to network failures. Historical log data is 1:1 with server log data in the long run (eventually consistent).

TODO
----

-   Create mock servers. Write two cheeky Python scripts that pipe output into test log files on two VirtualBox instances.
-   Write the highest-possible level config file an operator would use to configure Rill to monitor these two VirtualBox instances' log files.
    -   What boxes are you monitoring?
    -   What files do you want to monitor?    -   
    -   What parser will handle this log file? You need a separate process that talks over ZeroMQ to parse this data. This parse handles putting log data into the durable store.
    -   Durable store information.
-   Confirm ssh_tap works for the two log files. We need to output full lines, one ZeroMQ message per line, no parsing of lines.
-   Write a parser that hooks into the log files and outputs parsed data, i.e. a JSON pair (datetime, contents).
