package ai.agent

import akka.actor.ActorRef
import akka.event.Logging
import org.jivesoftware.smack._
import packet.{Packet, Message}
import org.jivesoftware.smackx.muc.{DiscussionHistory, MultiUserChat}
import org.jivesoftware.smack.provider.ProviderManager
import org.jivesoftware.smackx.provider.{MUCUserProvider, MUCAdminProvider, MUCOwnerProvider}
import org.jivesoftware.smackx.GroupChatInvitation
import org.jivesoftware.smackx.muc.{InvitationListener, ParticipantStatusListener, DefaultParticipantStatusListener}
import collection.JavaConversions._
import ai.agent.SmackConversions._
import akka.util.duration._
import akka.util.Timeout
import akka.dispatch.Await
import akka.dispatch.Future
import akka.pattern.ask
import akka.pattern.AskTimeoutException

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

case class XMPPAgentManager(agents: ActorRef*)(implicit config: Config)
    extends AgentManager(agents: _*)
    with ChatManagerListener
    with MessageListener
    with akka.actor.ActorLogging {

    override def postStop() {
        log.debug("postStop entry.")
        connection.disconnect()
    }

    log.debug("starting.")

    ServiceRegistryActor.ping(
        context = context,
        onSuccessCallback = result => {
            log.debug("Received ServiceRegistryPong. contents: %s".format(result.contents))
        },
        onExceptionCallback = exception => {
            log.error("serviceRegistry hit an exception")
            context.actorFor("/user/manager") ! akka.actor.PoisonPill
        }
    )

    // -------------------------------------------------------------------------
    //  In order to use the InvitationListener on MultiUserChat we need to
    //  set up the Providers. Typically this is done by default in a conf
    //  but we do it explicitly here.
    //
    //  Reference: http://community.igniterealtime.org/message/167897#167897 
    // -------------------------------------------------------------------------
    val pm = ProviderManager.getInstance
    pm.addExtensionProvider("x", "http://jabber.org/protocol/muc#user", new MUCUserProvider)
    pm.addIQProvider("query","http://jabber.org/protocol/muc#admin", new MUCAdminProvider)
    pm.addIQProvider("query","http://jabber.org/protocol/muc#owner", new MUCOwnerProvider)
    // -------------------------------------------------------------------------

    val login = config.setup
    import login._

    SmackConfiguration.setLocalSocks5ProxyEnabled(false)
    val connection = new XMPPConnection(serverType)
    connection.connect()
    connection.login(username, password)

    val rooms = MultiUserChat.getHostedRooms(connection, "conference.mink.datcon.co.uk")
    for (room <- rooms) {
        log.debug("get name")
        val name = room.getName()
        log.debug("get room info for name %s".format(name))
        val info = MultiUserChat.getRoomInfo(connection, name + "@conference.mink.datcon.co.uk")
        log.debug("room: %s, subject: %s, description: %s".format(info getRoom , info getSubject , info getDescription))
    }

    // ------------------------------------------------------------------------
    //  If someone invies us to a multi-user chat then unconditionally join
    //  the chat and output a message.
    // ------------------------------------------------------------------------
    MultiUserChat.addInvitationListener(connection, invitationListener)
    lazy val invitationListener = (e: InvitationListenerArguments) => {
        log.debug("invitationReceived. room: %s, inviter: %s, reason: %s, password: %s, message: %s".format(e.room, e.inviter, e.reason, e.password, e.message));
        var chat = new MultiUserChat(e.conn, e.room)
        var history = new DiscussionHistory()
        history.setMaxStanzas(0)
        val nickname = username.split("@").head
        chat.join(nickname, e.password, history, SmackConfiguration.getPacketReplyTimeout())
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
                log.debug("User who invited me left, so I'm leaving too.")
                chat.leave()
                chat.removeParticipantStatusListener(participantStatusListener)
                chat = null
                history = null
            }
        }
        // --------------------------------------------------------------------
    }
    // ------------------------------------------------------------------------
    
  connection.getChatManager.addChatListener(this)

  val roster: Roster = connection.getRoster()
  roster.setSubscriptionMode(Roster.SubscriptionMode.accept_all)

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


