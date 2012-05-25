# xmppbots

## Introduction

This application sets up a large number of XMPP bots, one per log file being tracked, and reports events in multi-user chats (MUCs) that are set up by users connected to the XMPP server. Written in Scala using Akka and Smack.

## Bugs

-   If a user's chat application crashes the bots don't realise the user has left. This is a combination of a) the server does not send out a ParticipantStatus update, b) the bots do not properly check if the user is still in the chat. Using chat.isJoined() is insufficient because this is just a flag that checks if we've every joined. Fix is to poll the participant list.
-   If the server destroys a MUC conference room the bot thinks its still connected. This is different from above. Fix is to poll the server's list of open MUC conferences and confirm the conference we are in is still in this list.
-   I've seen a weird asserts (term_acks > 0) in own.cpp in the ZeroMQ bindings. Presumably this causes the ConcurrentSocketActor handling ZeroMQ for Akka to crash. But this brings the whole house of cards crumbling, rather than a graceful restart. Worth some more testing by crashing the ZeroMQ bindings we SUBSCRIBE to.

