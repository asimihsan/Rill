package ai.agent

import org.jivesoftware.smack.Connection
import org.jivesoftware.smack.packet.{Packet, Message}
import org.jivesoftware.smackx.muc.{InvitationListener, ParticipantStatusListener, DefaultParticipantStatusListener}

object SmackConversions {

    case class InvitationListenerArguments(conn: Connection,
                                           room: String,
                                           inviter: String,
                                           reason: String,
                                           password: String,
                                           message: Message)
    implicit def functionToInvitationListener(f: InvitationListenerArguments => Unit) =
        new InvitationListener {
            override def invitationReceived(conn: Connection,
                                            room: String,
                                            inviter: String,
                                            reason: String,
                                            password: String,
                                            message: Message) =
                f(InvitationListenerArguments(conn, room, inviter, reason, password, message))
        }

    case class ParticipantStatusListenerArguments(participant: String, actor: Option[String], reason: Option[String])
    implicit def functionToParticipantStatusListener(f: ParticipantStatusListenerArguments => Unit) = 
        new DefaultParticipantStatusListener {
            override def left(participant: String) =
                f(ParticipantStatusListenerArguments(participant, None, None))
            override def kicked(participant: String, actor: String, reason: String) =
                f(ParticipantStatusListenerArguments(participant, Some(actor), Some(reason)))
            override def banned(participant: String, actor: String, reason: String) = 
                f(ParticipantStatusListenerArguments(participant, Some(actor), Some(reason)))
        }
}

