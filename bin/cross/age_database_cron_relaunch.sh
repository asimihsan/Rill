#!/usr/bin/env bash

SCRIPT_PATH="/usr/local/bin/python2.7 /root/ai/Rill/bin/cross/age_database.py"
if [[ $( echo `ps -eaf | egrep "${SCRIPT_PATH}" | egrep -v egrep | wc -l` ) -eq 0 ]];
then
    echo "will relaunch..."
    ${SCRIPT_PATH} > /dev/null 2> /dev/null < /dev/null &
fi

