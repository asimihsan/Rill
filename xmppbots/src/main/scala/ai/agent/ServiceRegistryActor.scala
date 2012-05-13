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
import net.liftweb.json.JsonAST.{JArray, JField, JObject, JString}
import net.liftweb.json.JsonParser
import java.io.{InputStreamReader, StringWriter, PrintWriter}

sealed class XmppBotMessage

case class ServiceRegistryGetHostnames(getListOfServicesURI: String) extends XmppBotMessage
case class ServiceRegistryGetServicesForHostname(hostname: String) extends XmppBotMessage
case class ServiceRegistryPing(contents: String) extends XmppBotMessage
case class ServiceRegistryPong(contents: String) extends XmppBotMessage

case class HTTPRequestGETRequest(URI: String) extends XmppBotMessage
case class HTTPRequestGETResponse(response: JObject) extends XmppBotMessage
case class HTTPRequestSuicide() extends XmppBotMessage

case class HTTPRequestException(cause: Exception) extends Exception
object Exceptions {
    def stackTraceToString(exception: Exception): String = {
        val sw = new StringWriter
        exception.printStackTrace(new PrintWriter(sw))
        sw.toString()
    }
}

object HTTPRequestActor {
    def getJSONFromURI(URI: String) = {
        try {
            Http(URI).
            option(HttpOptions.connTimeout(1000)).
            option(HttpOptions.readTimeout(5000)) { inputStream =>
                    val parsed = JsonParser.parse(new InputStreamReader(inputStream)).asInstanceOf[JObject]
                    parsed
            }
        } catch {
            case e: Exception => throw HTTPRequestException(e)
        } // try/catch
    } // def getJSONFromURI

    def get(context: ActorContext,
            actorPath: String,
            timeout: Duration = 5 seconds,
            URI: String,
            onSuccessCallback: (HTTPRequestGETResponse) => Unit,
            onExceptionCallback: (Exception) => Unit) = {

            val message = HTTPRequestGETRequest(URI)
            val future = context.actorFor(actorPath).ask(message)(timeout)
            future onComplete {
                case Right(result: HTTPRequestGETResponse) => onSuccessCallback(result) 
                case Left(exception: Exception) => onExceptionCallback(exception)
            }
            future
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
            try {
                val parsed = HTTPRequestActor.getJSONFromURI(URI)
                sender ! HTTPRequestGETResponse(parsed)
            } catch {
                case e: HTTPRequestException => 
                    sender ! akka.actor.Status.Failure(e)
            } // try/catch
        } // catch HTTPRequestGETRequest
    } // def receive
} // class HTTPRequestActor

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
    var getListOfServicesFailureCount = 0

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
            ActorSystem("XMPPBot").scheduler.scheduleOnce(10 seconds) {
                self ! ServiceRegistryGetHostnames(getListOfServicesURI)
            }
            val httpRequestActor = context.actorOf(Props(new HTTPRequestActor(getListOfServicesURI)))
            val future = HTTPRequestActor.get(
                context = context,
                actorPath = httpRequestActor.path.toString,
                URI = getListOfServicesURI,
                onSuccessCallback = result => {
                    //log.debug("ServiceRegistryGetHostnames responded: %s".format(result.response))
                    getListOfServicesFailureCount = 0
                    // TODO do stuff
                    httpRequestActor ! PoisonPill
                },
                onExceptionCallback = exception => {
                    exception match {
                        case HTTPRequestException(cause) => {
                            log.error("HTTPRequestException. stack trace:\n%s\ncause exception: %s. cause exception stack trace:\n%s".format(
                                Exceptions.stackTraceToString(exception),
                                cause,
                                Exceptions.stackTraceToString(cause)))
                            getListOfServicesFailureCount += 1
                        } // case HTTPRequestException
                    } // match exception
                    httpRequestActor ! PoisonPill
                }) // onExceptionCallback
        } // receive -> ServiceRegistryGetHostnames

        case ServiceRegistryPing(contents) => {
            log.debug("ServiceRegistryPing received. Contents: %s".format(contents))
            sender ! ServiceRegistryPong(contents) 
        }
    }
} // class ServiceRegistryActor

