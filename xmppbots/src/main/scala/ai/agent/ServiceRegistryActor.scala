package ai.agent

import akka.actor.Actor
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

import scalaj.http.{Http, HttpOptions}
import net.liftweb.json.JsonParser
import java.io.InputStreamReader

sealed class XmppBotMessage

case class ServiceRegistryGetHostnames(getListOfServicesURI: String) extends XmppBotMessage
case class ServiceRegistryGetServicesForHostname(hostname: String) extends XmppBotMessage
case class ServiceRegistryPing(contents: String) extends XmppBotMessage
case class ServiceRegistryPong(contents: String) extends XmppBotMessage

case class HTTPRequestGETRequest(URI: String) extends XmppBotMessage
case class HTTPRequestGETResponse() extends XmppBotMessage
case class HTTPRequestSuicide() extends XmppBotMessage

object HTTPRequestActor {
    def getJSONFromURI(URI: String) = {
        Http(URI).
        option(HttpOptions.connTimeout(1000)).
        option(HttpOptions.readTimeout(5000)) { inputStream =>
            val parsed = JsonParser.parse(new InputStreamReader(inputStream))
            parsed
        }
    }
}

case class HTTPRequestActor(URI: String)
    extends akka.actor.Actor
    with akka.actor.ActorLogging {

    override def preStart = {
        log.debug("preStart entry. URI: %s".format(URI))
        ActorSystem("XMPPBot").scheduler.scheduleOnce(10 seconds) {
            self ! PoisonPill
        }
    }

    override def postStop = {
        log.debug("postStop entry. URI: %s".format(URI))
    }

    log.debug("entry. URI: %s".format(URI))
    
    def receive = {
        case HTTPRequestGETRequest(URI) => {
            val parsed = HTTPRequestActor.getJSONFromURI(URI)
            log.debug("parsed: %s".format(parsed))
        }
    }
}

object ServiceRegistryActor {
    def ping(context: ActorContext,
             actorPath: String = "/user/serviceRegistry",
             timeout: Duration = 5 seconds,
             contents: String = "hello",
             onSuccessCallback: (ServiceRegistryPong) => Unit,
             onAskTimeoutExceptionCallback: (AskTimeoutException) => Unit) = {

            val message = ServiceRegistryPing(contents)
            val future = context.actorFor(actorPath).ask(message)(timeout)
            future onComplete {
                case Right(result: ServiceRegistryPong) => onSuccessCallback(result) 
                case Left(exception: AskTimeoutException) => onAskTimeoutExceptionCallback(exception)
            }
            future
        }

    def getListOfServices(listOfServicesURI: String) = {
        
    }
}

case class ServiceRegistryActor(serviceRegistryURI: String)
    extends Actor
    with akka.actor.ActorLogging {

    val getListOfServicesURI = "%s/list_of_services".format(serviceRegistryURI)

    override def preStart = {
        log.debug("preStart entry.")
        self ! ServiceRegistryGetHostnames(getListOfServicesURI)
    }

    override def postStop = {
        log.debug("postStop entry.")
    }

    def receive = {
        case ServiceRegistryGetHostnames(getListOfServicesURI) => {
            log.debug("ServiceRegistryGetHostnames received.")
            val httpRequestActor = context.actorOf(Props(new HTTPRequestActor(getListOfServicesURI)))
            httpRequestActor ! HTTPRequestGETRequest(getListOfServicesURI)
        }
        case ServiceRegistryPing(contents) => {
            log.debug("ServiceRegistryPing received. Contents: %s".format(contents))
            sender ! ServiceRegistryPong(contents) 
        }
    }
} // class ServiceRegistryActor

