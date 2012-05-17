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
                               SubscribeAll)
        subSocket ! NoLinger
        log.debug("created subSocket")
        destinationActor = bot.botRef
        // -----------------------------------------------------------------------
    } // def preStart

    override def postStop = {
        log.debug("postStop entry.")
    }

    def receive = {
        case m: akka.zeromq.ZMQMessage => {
            val rawPayload = m.firstFrameAsString
            val decodedPayload = JsonParser.parse(rawPayload).asInstanceOf[JObject]
            var contents = decodedPayload
                           .values
                           .get("contents")
            contents match {
                case Some(elem) => destinationActor ! BotSubscriptionMessage(elem.toString)
                case None => log.warning("got ZMQ message payload without contents: %s".format(rawPayload))
            }
        } // case ZMQMessage
        case BotStopSubscriptionMessage => {
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

