#!/usr/bin/env bash

/root/ai/Rill/bin/cross/create_bot_users.py
cd /root/ai/Rill/xmppbots/
sbt run | tee /var/log/rill/rill_xmppbots_gc.log

