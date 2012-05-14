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

import scala.collection.mutable.ListBuffer
import scala.util.Sorting

sealed class XmppBotMessage

case class ServiceRegistryUpdateServices(getListOfServicesURI: String) extends XmppBotMessage
case class ServiceRegistryGetServices() extends XmppBotMessage
case class ServiceRegistryGetServicesResponse(services: List[Service]) extends XmppBotMessage
case class ServiceRegistryPing(contents: String) extends XmppBotMessage
case class ServiceRegistryPong(contents: String) extends XmppBotMessage

case class Service(parserName: String, binding: String) extends Ordered[Service] {
    override def toString = "{Service: parserName: %s, binding: %s".format(parserName, binding)
    def compare(that: Service) = parserName compare that.parserName
}

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
             onExceptionCallback: (Exception) => Unit) = {

            val message = ServiceRegistryPing(contents)
            val future = context.actorFor(actorPath).ask(message)(timeout)
            future onComplete {
                case Right(result: ServiceRegistryPong) => onSuccessCallback(result) 
                case Left(exception: Exception) => onExceptionCallback(exception)
            }
            future
        }

    def getListOfServices(context: ActorContext,
                          actorPath: String = "/user/serviceRegistry",
                          timeout: Duration = 5 seconds,
                          contents: String = "hello",
                          onSuccessCallback: (ServiceRegistryGetServicesResponse) => Unit,
                          onExceptionCallback: (Exception) => Unit) = {

            val message = ServiceRegistryGetServices()
            val future = context.actorFor(actorPath).ask(message)(timeout)
            future onComplete {
                case Right(result: ServiceRegistryGetServicesResponse) => onSuccessCallback(result) 
                case Left(exception: Exception) => onExceptionCallback(exception)
            }
            future
        }
}

case class ServiceRegistryActor(serviceRegistryURI: String)
    extends Actor
    with akka.actor.ActorLogging {

    val getListOfServicesURI = "%s/list_of_services".format(serviceRegistryURI)
    var getListOfServicesFailureCount = 0
    var services: List[Service] = List()

    override def preStart = {
        log.debug("preStart entry.")
        self ! ServiceRegistryUpdateServices(getListOfServicesURI)
    }

    override def postStop = {
        log.debug("postStop entry.")
    }

    def receive = {
        // -------------------------------------------------------------------
        //  Return the list of services that we know about.
        // -------------------------------------------------------------------
        case ServiceRegistryGetServices => sender ! ServiceRegistryGetServicesResponse(services)
        // -------------------------------------------------------------------

        // -------------------------------------------------------------------
        //  Get a list of services from the service registry once every
        //  10 seconds and then stash the result. 
        // -------------------------------------------------------------------
        case ServiceRegistryUpdateServices(getListOfServicesURI) => {
            log.debug("ServiceRegistryUpdateServices received.")
            ActorSystem("XMPPBot").scheduler.scheduleOnce(10 seconds) {
                self ! ServiceRegistryUpdateServices(getListOfServicesURI)
            }
            val httpRequestActor = context.actorOf(Props(new HTTPRequestActor(getListOfServicesURI)))
            val future = HTTPRequestActor.get(
                context = context,
                actorPath = httpRequestActor.path.toString,
                URI = getListOfServicesURI,
                onSuccessCallback = result => {
                    // -------------------------------------------------------
                    //  We have a JObject in result.response, which is the
                    //  parsed JSON of the list of services. Turn this into a
                    //  Map and stash it. 
                    // -------------------------------------------------------
                    //log.debug("ServiceRegistryUpdateServices responded: %s".format(result.response))
                    var newServices: ListBuffer[Service] = ListBuffer()
                    result.response.values.foreach {
                        case (parserName, binding) => {
                            newServices += Service(parserName, binding.toString)
                        }
                    }
                    newServices = newServices.sortWith((e1, e2) => (e1 < e2))
                    if (!newServices.corresponds(services){_ == _}) {
                        services = newServices.toList
                        log.debug("services changed to %s.".format(services))
                    }
                    getListOfServicesFailureCount = 0
                    httpRequestActor ! PoisonPill
                    // -------------------------------------------------------
                },
                onExceptionCallback = exception => {
                    getListOfServicesFailureCount += 1
                    exception match {
                        case HTTPRequestException(cause) => {
                            log.error("HTTPRequestException. stack trace:\n%s\ncause exception: %s. cause exception stack trace:\n%s".format(
                                Exceptions.stackTraceToString(exception),
                                cause,
                                Exceptions.stackTraceToString(cause)))
                        } // case HTTPRequestException
                        //case AskTimeoutException => {
                        //    log.error("AskTimeoutException. stack trace:\n%s".format(Exceptions.stackTraceToString(exception)))
                        //}
                    } // match exception
                    httpRequestActor ! PoisonPill
                }) // onExceptionCallback
        } // receive -> ServiceRegistryUpdateServices
        // -------------------------------------------------------------------

        case ServiceRegistryPing(contents) => {
            log.debug("ServiceRegistryPing received. Contents: %s".format(contents))
            sender ! ServiceRegistryPong(contents) 
        }
    }
} // class ServiceRegistryActor

