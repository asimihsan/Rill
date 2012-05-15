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
import packet.{Packet, Message}
import org.jivesoftware.smackx.muc.{DiscussionHistory, MultiUserChat}
import org.jivesoftware.smack.provider.ProviderManager
import org.jivesoftware.smackx.provider.{MUCUserProvider, MUCAdminProvider, MUCOwnerProvider}
import org.jivesoftware.smackx.GroupChatInvitation
import org.jivesoftware.smackx.muc.{InvitationListener, ParticipantStatusListener, DefaultParticipantStatusListener}

import net.liftweb.json.JsonAST.{JArray, JField, JObject, JString}
import net.liftweb.json.JsonParser

import ai.agent.SmackConversions._
import collection.JavaConversions._
import scala.collection.mutable.ListBuffer

case class ChatSink(chat: Chat, connection: XMPPConnection) extends Sink {
  override def output(ans: Any) = {
    val msg = new Message(chat.getParticipant, Message.Type.chat)
    msg.setBody(ans.toString)
    connection.sendPacket(msg)
  }
}

case class GroupChatSink(chat: MultiUserChat) extends Sink {
  override def output(ans: Any) = {
    chat.sendMessage(ans.toString)
  }
}

sealed class BotMessage
case class BotStartMessage() extends BotMessage
case class BotSubscriptionMessage(message: String) extends BotMessage
case class BotStopSubscription() extends BotMessage

case class ZeroMQSubscriptionActor(bot: Bot)
    extends Actor
    with akka.actor.ActorLogging {

    val system: ActorSystem = ActorSystem("XMPPBot")
    var subSocket: ActorRef = null
    var destinationActor: ActorRef = null

    log.debug("starting.")

    override def preStart = {
        log.debug("preStart entry.")
        // -----------------------------------------------------------------------
        //  Initialize local variables.
        // -----------------------------------------------------------------------
        subSocket = ZeroMQExtension(system)
                    .newSocket(SocketType.Sub,
                               Listener(self),
                               Connect(bot.binding),
                               Subscribe(""))
        subSocket ! Linger(0)
        log.debug("created subSocket")
        destinationActor = bot.actorRef
        // -----------------------------------------------------------------------
    } // def preStart

    override def postStop = {
        log.debug("postStop entry.")
    }

    def receive = {
        case m: akka.zeromq.ZMQMessage => {
            val rawPayload = m.firstFrameAsString
            val decodedPayload = JsonParser.parse(rawPayload).asInstanceOf[JObject]
            var contents: String = null
            decodedPayload.values.foreach {
                case (key, value) => {
                    if (key == "contents") {
                        contents = value.toString
                    }
                }
            }
            //log.debug("got ZMQ message payload: %s".format(contents))
            destinationActor ! BotSubscriptionMessage(contents)
        } // case ZMQMessage
        case BotStopSubscription => {
            log.debug("Received BotStopSubscription message.")
            subSocket ! PoisonPill
            //system stop subSocket
        }
        case m => {
            if (m == akka.zeromq.ZeroMQ.connecting())
                log.debug("Connecting message received for the SubSocket")
            if (m == akka.zeromq.ZeroMQ.closed())
                log.debug("Closed message received for the SubSocket")
        }
    } // def receive
} // class ZeroMQSubscriptionActor

case class Bot(service: Service, actorRef: ActorRef) {
    val parserName = service.parserName
    val binding = service.binding

    def server = "mink.datcon.co.uk"
    def conferenceServer = "conference.%s".format(server)
    def username = "%s@%s".format(parserName, server)
    def password = parserName
    def nickname = parserName
    
    override def toString = "{Bot: server=%s, username=%s, password=%s, nickname=%s}".format(
        server,username, password, nickname)
}

class BotActor(service: Service)
    extends Actor
    with ChatManagerListener
    with MessageListener
    with akka.actor.ActorLogging {

    // -----------------------------------------------------------------------
    //  Initialize local variables.
    // -----------------------------------------------------------------------
    val bot = new Bot(service = service, actorRef = self)
    var connection: XMPPConnection = null
    val chats: ListBuffer[MultiUserChat] = ListBuffer()
    var zeroMQSubscriptionActor: ActorRef = null
    // -----------------------------------------------------------------------

    def addChat(chat: MultiUserChat) = {
        chats += chat
        if (chats.length == 1) {
            log.debug("first chat added, so start ZeroMQ actor.")
            zeroMQSubscriptionActor = context.actorOf(Props(new ZeroMQSubscriptionActor(bot)),
                                                     name = "z")
        }
    } // addChat

    def removeChat(chat: MultiUserChat) = {
        chats.remove(chats.indexOf(chat))
        if (chats.length == 0) {
            log.debug("no chats left, so stop ZeroMQ actor.")
            if (zeroMQSubscriptionActor != null) {
                log.debug("found ZeroMQ actor, so kill it.")
                zeroMQSubscriptionActor ! BotStopSubscription
                zeroMQSubscriptionActor ! PoisonPill
                zeroMQSubscriptionActor = null
            }
        }
    } // removeChat

    override def preStart = {
        log.debug("preStart entry.")
        self ! BotStartMessage()
    }

    override def postStop = {
        log.debug("postStop entry.")
        require(connection != null)
        connection.disconnect()
    }

    override def receive = {
        case BotStartMessage() => initialize
        case BotSubscriptionMessage(message) => {
            require(chats.length > 0)
            for (chat <- chats) {
                chat.sendMessage(message)
            }
        } // case BotSubscriptionMessage
    } // def receive

    def initialize = {
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
            
        SmackConfiguration.setLocalSocks5ProxyEnabled(false)
        connection = new XMPPConnection(bot.server)
        connection.connect()
        connection.login(bot.username, bot.password)

        /*
        val rooms = MultiUserChat.getHostedRooms(connection, bot.conferenceServer)
        for (room <- rooms) {
            log.debug("get name")
            val name = room.getName()
            log.debug("get room info for name %s".format(name))
            val info = MultiUserChat.getRoomInfo(connection, name + "@conference.mink.datcon.co.uk")
            log.debug("room: %s, subject: %s, description: %s".format(info getRoom , info getSubject , info getDescription))
        }
        */

        // ------------------------------------------------------------------------
        //  If someone invies us to a multi-user chat then unconditionally join
        //  the chat and output a message.
        // ------------------------------------------------------------------------
        MultiUserChat.addInvitationListener(connection, invitationListener)
        lazy val invitationListener = (e: InvitationListenerArguments) => {
            log.debug("invitationReceived. room: %s, inviter: %s, reason: %s, password: %s, message: %s".format(e.room, e.inviter, e.reason, e.password, e.message));
            var chat = new MultiUserChat(e.conn, e.room)
            addChat(chat)
            var history = new DiscussionHistory()
            history.setMaxStanzas(0)
            chat.join(bot.nickname, e.password, history, SmackConfiguration.getPacketReplyTimeout())
            chat.sendMessage("i spam, therefore i am")
            val inviterAsParticipant = "%s/%s".format(e.room, e.inviter.split("@").head)

            // --------------------------------------------------------------------
            //  If the inviter leaves then we want to leave as well. Note:
            //  this is flaky, so in the background poll the participants of the
            //  room and leave if the inviter is no longer part of that list.
            // --------------------------------------------------------------------
            chat.addParticipantStatusListener(participantStatusListener)
            lazy val participantStatusListener: ParticipantStatusListener = (e: ParticipantStatusListenerLeftArguments) => {
                log.debug("ParticipantStatusListener: participant %s left.".format(e.participant))
                if (e.participant == inviterAsParticipant) {
                    log.debug("User %s who invited me left, so I'm leaving too.".format(e.participant))
                    removeChat(chat)
                    chat.leave()
                    chat.removeParticipantStatusListener(participantStatusListener)
                    chat = null
                    history = null
                }
            } // participantStatusListener
            // --------------------------------------------------------------------
        } // inivtationListener
        // ------------------------------------------------------------------------
        
        connection.getChatManager.addChatListener(this)

        val roster: Roster = connection.getRoster()
        roster.setSubscriptionMode(Roster.SubscriptionMode.accept_all)
    } // initialize()

  /*
  chat.addMessageListener(new PacketListener() {
    def processPacket(packet: Packet) {
      packet match {
        case m: Message => {
          log.debug("got the following message: %s".format(m.getBody))
          self !(m.getBody, GroupChatSink(chat))
        }
      }
    }
  })
  */

  //Listen & Forward Messages
  override def chatCreated(chat: Chat, locally: Boolean) {
    //chat.addMessageListener(this)
  }

  override def processMessage(chat: Chat, message: Message) {
    //self !(message.getBody, ChatSink(chat, connection))
  }

}
