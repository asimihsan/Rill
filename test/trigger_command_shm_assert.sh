#!/usr/bin/env bash
/root/ai/Rill/test/trigger_command.py --hostname_regexp shm --log_regexp "Assertion failed" --command "/usr/local/bin/python2.7 /root/ai/sendemail.py from=mink@intranet.datcon.co.uk to=ai@intranet.datcon.co.uk sub='Assertion failed on \${hostname}' body='\${contents}'" --verbose
