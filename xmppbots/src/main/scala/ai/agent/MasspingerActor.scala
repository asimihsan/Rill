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

import net.liftweb.json.JsonAST.{JArray, JField, JObject, JString}
import net.liftweb.json.JsonParser

import scala.collection._

sealed class MasspingerMessage
case class BotSubscribingToMasspingerMessage(bot: Bot) extends MasspingerMessage

class BotAndResponsiveness(botInput: Bot) extends Ordered[BotAndResponsiveness] {
    var bot: Bot = botInput
    var isResponsive: Boolean = false
    override def toString = "{BotAndResponsiveness. bot=%s, isResponsvive=%s}".format(bot, isResponsive)
    override def compare(that: BotAndResponsiveness) = bot compare that.bot
}

case class MasspingerActor(masspingerService: Service)
    extends Actor
    with akka.actor.ActorLogging {

    val system: ActorSystem = ActorSystem("XMPPBot")
    var subSocket: ActorRef = null
    var mapHostnameToBots: mutable.HashMap[String, mutable.Set[BotAndResponsiveness]] = new mutable.HashMap()

    log.debug("starting.")

    override def preStart = {
        log.debug("preStart entry.")
        // -----------------------------------------------------------------------
        //  Initialize local variables.
        // -----------------------------------------------------------------------
        subSocket = ZeroMQExtension(system)
                    .newSocket(SocketType.Sub,
                               Listener(self),
                               Connect(masspingerService.binding),
                               SubscribeAll)
        subSocket ! NoLinger
        log.debug("created subSocket")
        // -----------------------------------------------------------------------
    } // def preStart

    override def postStop = {
        log.debug("postStop entry.")
        subSocket ! PoisonPill
    }

    def areValidMessageFrames(frames: Seq[String]): Boolean = {
        if (frames.length != 2) false
        else if (frames(1) != "responsive" && frames(1) != "unresponsive") false
        else true
    }

    override def receive = {
        case BotSubscribingToMasspingerMessage(bot) => {
            log.debug("BotSubscribingtoMasspingerMessage received for bot: %s".format(bot))
            bot.botRef ! BotIsDeadMessage()
            val botToInsert = new BotAndResponsiveness(bot)
            if (mapHostnameToBots contains bot.hostname) {
                mapHostnameToBots(bot.hostname) += botToInsert
            } else {
                mapHostnameToBots += (bot.hostname -> mutable.Set(botToInsert))
            }
        }

        case m: akka.zeromq.ZMQMessage => {
            val frames = m.frames.map(frame => new String(frame.payload.toArray, "UTF-8"))
            if (!areValidMessageFrames(frames)) {
                log.warning("Received invalid masspinger message: %s".format(frames))
            } else {
                val hostname = frames(0)
                val isResponsive = (frames(1) == "responsive")
                if (mapHostnameToBots contains hostname) {
                    for {
                        bot <- mapHostnameToBots(hostname)
                        if (bot.isResponsive ^ isResponsive)
                    } {
                        //log.debug("bot %s used to be %s, but is now %s".format(bot, bot.isResponsive, isResponsive))
                        bot.isResponsive = isResponsive
                        if (isResponsive)
                            bot.bot.botRef ! BotIsAliveMessage()
                        else
                            bot.bot.botRef ! BotIsDeadMessage()
                    } // if responsiveness has changed
                } // if we know who this host is
            } // if the message is valid
        } // case ZMQMessage
    } // def receive

} // class MasspingerActor
