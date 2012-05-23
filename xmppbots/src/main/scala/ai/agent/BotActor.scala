package ai.agent

import akka.actor.Actor
import akka.actor.ActorPath
import akka.actor.ActorRef
import akka.actor.Props
import akka.event.Logging
import akka.dispatch.Future
import akka.pattern.AskTimeoutException
import akka.util.duration._
import akka.util.Duration
import akka.actor.ActorContext
import akka.pattern.ask
import akka.actor.ActorSystem
import akka.actor.PoisonPill
import akka.zeromq._

import org.jivesoftware.smack._
import packet.{Packet, Message, Presence}
import org.jivesoftware.smackx.muc.{DiscussionHistory, MultiUserChat}
import org.jivesoftware.smack.provider.ProviderManager
import org.jivesoftware.smackx.provider.{MUCUserProvider, MUCAdminProvider, MUCOwnerProvider}
import org.jivesoftware.smackx.GroupChatInvitation
import org.jivesoftware.smackx.muc.{InvitationListener, ParticipantStatusListener, DefaultParticipantStatusListener}

import net.liftweb.json.JsonAST.{JArray, JField, JObject, JString}
import net.liftweb.json.JsonParser

import ai.agent.SmackConversions._
import collection.JavaConversions._
import scala.collection.mutable.LinkedHashSet
import scala.util.matching.Regex
import dk.brics.automaton

sealed class BotMessage
case class BotStartMessage() extends BotMessage
case class BotSubscriptionMessage(message: String) extends BotMessage
case class BotStopSubscriptionMessage() extends BotMessage
case class BotCheckIfStillInChatsMessage() extends BotMessage
case class BotIsAliveMessage() extends BotMessage
case class BotIsDeadMessage() extends BotMessage

case class BotActor(service: Service, masspinger: ActorRef)
    extends Actor
    with akka.actor.ActorLogging {

    // -----------------------------------------------------------------------
    //  Initialize local variables.
    // -----------------------------------------------------------------------
    val bot = new Bot(service = service, actorRef = self)
    var connection: XMPPConnection = null
    val chats: LinkedHashSet[MultiUserChat] = LinkedHashSet()
    var zeroMQSubscriptionActor: ActorRef = null
    val defaultRegexString = Seq("Assertion.*failed",
                                 "Unhandled exception",
                                 "signal 11",
                                 "Metaswitch check failed",
                                 "detected a deadlock",
                                 "Exception caught on signal",
                                 "Config stub is starting",
                                 "vp3craft.*Run script",
                                 "DC_ASSERT",
                                 "EP REBOOT REASON",
                                 "fatal kernel task-level exception",
                                 "Request to use ISDN signaling ID that is already in use",
                                 "Request to use GR-303 signaling ID that is already in use",
                                 "Request to use SS7 signaling ID that is already in use",
                                 "HDLCmgr is out of ISDN NAIs",
                                 "shm_reboot").mkString(".*(", "|", ").*")
    val defaultRegex = defaultRegexString.r
    //val defaultRegex = new automaton.RegExp(defaultRegexString).toAutomaton();
    //val defaultRegex = new automaton.RunAutomaton(new automaton.RegExp(defaultRegexString).toAutomaton());
    // -----------------------------------------------------------------------

    def addChat(chat: MultiUserChat) = {
        log.debug("addChat entry. chat: %s".format(chat))
        require(chat != null)
        chats += chat
        if (chats.size == 1) {
            log.debug("first chat added, so start ZeroMQ actor.")
            zeroMQSubscriptionActor = context.actorOf(Props(new ZeroMQSubscriptionActor(bot)),
                                                     name = "z")
        }
        log.debug("addChat exit.")
    } ensuring (chats contains chat) // addChat

    def removeChat(chat: MultiUserChat) = {
        log.debug("removeChat entry. chat: %s".format(chat))
        require(chat != null)
        require(chats contains chat)
        chats.remove(chat)
        if (chats.size == 0) {
            log.debug("no chats left, so stop ZeroMQ actor.")
            if (zeroMQSubscriptionActor != null) {
                log.debug("found ZeroMQ actor, so kill it.")
                zeroMQSubscriptionActor ! BotStopSubscriptionMessage
                zeroMQSubscriptionActor ! PoisonPill
                zeroMQSubscriptionActor = null
            }
        }
        log.debug("removeChat exit.")
    } ensuring (!(chats contains chat)) // removeChat

    def processCommand(command: String) = {
        require(command startsWith "$%s".format(bot.nickname))
        log.debug("processCommand entry. command: %s".format(command))
    } // def processCommand

    override def preStart = {
        log.debug("preStart entry.")
        self ! BotStartMessage()
    }

    override def postStop = {
        log.debug("postStop entry.")
        require(connection != null)
        connection.disconnect()
    }

    def sendPresence(isAlive: Boolean) {
        val packet = new Presence(Presence.Type.available)
        if (isAlive)
            packet.setMode(Presence.Mode.available)
        else
            packet.setMode(Presence.Mode.away)
        connection.sendPacket(packet)
        for (chat <- chats)
            if (isAlive)
                chat.sendMessage("I used to be non-pingable, but now I am pingable.")
            else
                chat.sendMessage("I used to be pingable, but now I am not.")
    }

    override def receive = {
        case BotStartMessage() => {
            initialize

            // ---------------------------------------------------------------
            // Check once every 10 seconds that we're sill in each of the
            // chats we think we are in.
            // ---------------------------------------------------------------
            ActorSystem("XMPPBot").scheduler.schedule(
                0 seconds,
                10 seconds,
                self,
                BotCheckIfStillInChatsMessage())
            // ---------------------------------------------------------------

            masspinger ! BotSubscribingToMasspingerMessage(bot)

        } // case BotStartMessage

        case BotCheckIfStillInChatsMessage() => {
            val orphanChats = chats.filter( chat => !(chat.isJoined()) )
            for (chat <- orphanChats) {
                log.debug("still tracking chat %s that we're not part of.".format(chat))
                removeChat(chat)
            } // for chat in orphanChats
        } // case BotCheckIfStillInChatsMessage

        // -------------------------------------------------------------------
        //  Got a message from the ZeroMQ actor.
        //
        //  !!AI TODO hack of hacks. Just regexp it here, use the Chat
        //  class later.
        // -------------------------------------------------------------------
        case BotSubscriptionMessage(message) => {
            if (chats.size <= 0) {
                log.error("received BotSubscriptionMessage, but no chats are open! Message: %s".format(message))
            }
            require(chats.size > 0)
            if (((defaultRegex findFirstIn message) isEmpty) == false) {
            //if ((defaultRegex.run(message))) {
                for (chat <- chats) {
                    chat.sendMessage(message)
                }
            }
        } // case BotSubscriptionMessage
        // -------------------------------------------------------------------
        
        // -------------------------------------------------------------------
        //  Presence updates. Only masspinger sends us these messages.
        // -------------------------------------------------------------------
        case BotIsAliveMessage() => sendPresence(isAlive = true)
        case BotIsDeadMessage() =>  sendPresence(isAlive = false)
        // -------------------------------------------------------------------

    } // def receive

    def initialize: Unit = {
        // ----------------------------------------------------------------
        //  In order to use the InvitationListener on MultiUserChat we need to
        //  set up the Providers. Typically this is done by default in a conf
        //  but we do it explicitly here.
        //
        //  Reference: http://community.igniterealtime.org/message/167897#167897 
        // ----------------------------------------------------------------
        val pm = ProviderManager.getInstance
        pm.addExtensionProvider("x", "http://jabber.org/protocol/muc#user", new MUCUserProvider)
        pm.addIQProvider("query","http://jabber.org/protocol/muc#admin", new MUCAdminProvider)
        pm.addIQProvider("query","http://jabber.org/protocol/muc#owner", new MUCOwnerProvider)
        // ----------------------------------------------------------------
            
        // ------------------------------------------------------------------------
        //  Connect.
        // ------------------------------------------------------------------------
        SmackConfiguration.setLocalSocks5ProxyEnabled(false)
        connection = new XMPPConnection(bot.server)
        connection.connect()
        connection.login(bot.username, bot.password)
        // ------------------------------------------------------------------------

        // ------------------------------------------------------------------------
        //  Unconditionally accept invites.
        // ------------------------------------------------------------------------
        val roster: Roster = connection.getRoster()
        roster.setSubscriptionMode(Roster.SubscriptionMode.accept_all)
        // ------------------------------------------------------------------------

        // ------------------------------------------------------------------------
        //  If someone invies us to a multi-user chat then unconditionally join
        //  the chat and output a message.
        // ------------------------------------------------------------------------
        MultiUserChat.addInvitationListener(connection, invitationListener)
        lazy val invitationListener = (e: InvitationListenerArguments) => {
            log.debug("invitationReceived. room: %s, inviter: %s, reason: %s, password: %s, message: %s".format(e.room, e.inviter, e.reason, e.password, e.message));
            var chat = new MultiUserChat(e.conn, e.room)
            val inviterAsParticipant = "%s/%s".format(e.room, e.inviter.split("@").head)
            val meAsParticipant = "%s/%s".format(e.room, bot.username.split("@").head)

            // ---------------------------------------------------------------
            // chat.isJoined() only tells you if you've called chat.join() yet;
            // it _does not_ tell you if you've ever joined this particular
            // chat before. We need to determine this for ourselves.
            // ---------------------------------------------------------------
            if (chats.map(chat => chat.getRoom()).contains(e.room)) {
                log.debug("Already inside chat, so no need to join again.")
                return
            }
            // ---------------------------------------------------------------
            //
            addChat(chat)
            var history = new DiscussionHistory()
            history.setMaxStanzas(0)
            chat.join(bot.nickname, e.password, history, SmackConfiguration.getPacketReplyTimeout())
            chat.sendMessage("i spam, therefore i am")
            log.debug("inviterAsParticipant: %s. meAsParticipant: %s".format(inviterAsParticipant, meAsParticipant))

            // --------------------------------------------------------------------
            //  If the inviter leaves then we want to leave as well. Note:
            //  this is flaky, so in the background poll the participants of the
            //  room and leave if the inviter is no longer part of that list.
            //
            //  Also, if we are kicked or banned then we do not receive
            //  notification fo this, so we need to poll in the background
            //  anyway.
            // --------------------------------------------------------------------
            chat.addParticipantStatusListener(participantStatusListener)
            lazy val participantStatusListener: ParticipantStatusListener = (e: ParticipantStatusListenerArguments) => {
                log.debug("ParticipantStatusListener: participant %s left.".format(e.participant))
                if (e.participant == inviterAsParticipant) {
                    log.debug("User %s has left chat.".format(e.participant))
                    chat.leave()
                    chat.removeParticipantStatusListener(participantStatusListener)
                    removeChat(chat)
                    chat = null
                    history = null
                }
            } // participantStatusListener
            // --------------------------------------------------------------------
            
            // --------------------------------------------------------------------
            //  Process messages within a multi user chat.
            //
            //  !!AI Actually no, don't. This leads to O(n^2) increase in
            //  processing cost with no benefit, where n is number of bots in
            //  chat. I don't want this! Use private messages!!
            // --------------------------------------------------------------------
            //chat.addMessageListener(messageListener)
            lazy val messageListener = (e: MessageListenerArguments) => {
                val body = e.message.getBody()
                val indicator = "$%s".format(bot.nickname)
                for {
                    line <- body.split("\n")
                    if line startsWith indicator
                } {
                    log.debug("seen message in chat for me: '%s'".format(line))
                    processCommand(line)
                }
            } // messageListener
            // --------------------------------------------------------------------
            
        } // inivtationListener
        // ------------------------------------------------------------------------

        // connection.getChatManager.addChatListener(this)

    } // initialize()

}
