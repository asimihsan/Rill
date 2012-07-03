#!/usr/bin/env bash
/root/ai/Rill/test/trigger_command.py --hostname_regexp ngmg_ep --log_regexp "EP REBOOT" --command "/usr/local/bin/python2.7 /root/ai/sendemail.py from=mink@intranet.datcon.co.uk to=ai@intranet.datcon.co.uk,bsa@intranet.datcon.co.uk sub='EP REBOOT on \${hostname}' body='\${contents}'" --verbose
