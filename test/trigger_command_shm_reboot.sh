#!/usr/bin/env bash
/root/ai/Rill/test/trigger_command.py --hostname_regexp shm_messages --log_regexp "shm_reboot" --command "/usr/local/bin/python2.7 /root/ai/sendemail.py from=mink@intranet.datcon.co.uk to=ai@intranet.datcon.co.uk sub='shm_reboot on \${hostname}' body='\${contents}'" --verbose
