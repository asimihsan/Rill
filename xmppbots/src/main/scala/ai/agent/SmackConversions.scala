package ai.agent

import org.jivesoftware.smack.Connection
import org.jivesoftware.smack.packet.{Packet, Message}
import org.jivesoftware.smackx.muc.{InvitationListener, DefaultParticipantStatusListener}

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

    case class ParticipantStatusListenerLeftArguments(participant: String)
    implicit def functionToParticipantStatusListenerLeft(f: ParticipantStatusListenerLeftArguments => Unit) = 
        new DefaultParticipantStatusListener {
            override def left(participant: String) =
                f(ParticipantStatusListenerLeftArguments(participant))
        }

}

