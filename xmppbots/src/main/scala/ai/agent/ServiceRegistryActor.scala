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

import scala.collection.mutable.ListBuffer
import scala.util.Sorting

import java.io.InputStreamReader

sealed class ServiceRegistryMessage
case class ServiceRegistryUpdateServices(getServicesURI: String) extends ServiceRegistryMessage
case class ServiceRegistryGetServices() extends ServiceRegistryMessage
case class ServiceRegistryGetServicesResponse(services: List[Service]) extends ServiceRegistryMessage
case class ServiceRegistryPing(contents: String) extends ServiceRegistryMessage
case class ServiceRegistryPong(contents: String) extends ServiceRegistryMessage

case class HTTPRequestGETRequest(URI: String) extends ServiceRegistryMessage
case class HTTPRequestGETResponse(response: JObject) extends ServiceRegistryMessage
case class HTTPRequestSuicide() extends ServiceRegistryMessage

case class HTTPRequestException(cause: Exception) extends Exception

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

    def getServices(context: ActorContext,
                    actorPath: String = "/user/serviceRegistry",
                    timeout: Duration = 5 seconds,
                    onSuccessCallback: (ServiceRegistryGetServicesResponse) => Unit,
                    onExceptionCallback: (Exception) => Unit) = {
            val system = ActorSystem("XMPPBot")
            system.log.info("getServices entry.")

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

    val getServicesURI = "%s/list_of_services".format(serviceRegistryURI)
    var getServicesFailureCount = 0
    var services: List[Service] = List()

    override def preStart = {
        log.debug("preStart entry.")
        self ! ServiceRegistryUpdateServices(getServicesURI)
    }

    override def postStop = {
        log.debug("postStop entry.")
    }

    override def receive = {
        // -------------------------------------------------------------------
        //  Return the list of services that we know about.
        // -------------------------------------------------------------------
        case ServiceRegistryGetServices() => {
            log.debug("ServiceRegistryGetServices message received from: %s.".format(sender))
            sender ! ServiceRegistryGetServicesResponse(services)
        }
        // -------------------------------------------------------------------
        //
        case ServiceRegistryPing(contents) => {
            log.debug("ServiceRegistryPing received. Contents: %s".format(contents))
            sender ! ServiceRegistryPong(contents) 
        }

        // -------------------------------------------------------------------
        //  Get a list of services from the service registry once every
        //  10 seconds and then stash the result. 
        // -------------------------------------------------------------------
        case ServiceRegistryUpdateServices(getServicesURI) => {
            log.debug("ServiceRegistryUpdateServices received.")
            /*
            ActorSystem("XMPPBot").scheduler.scheduleOnce(10 seconds) {
                self ! ServiceRegistryUpdateServices(getServicesURI)
            }
            */
            val httpRequestActor = context.actorOf(Props(new HTTPRequestActor(getServicesURI)))
            val future = HTTPRequestActor.get(
                context = context,
                actorPath = httpRequestActor.path.toString,
                URI = getServicesURI,
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
                    getServicesFailureCount = 0
                    httpRequestActor ! PoisonPill
                    // -------------------------------------------------------
                },
                onExceptionCallback = exception => {
                    getServicesFailureCount += 1
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

    }
} // class ServiceRegistryActor

