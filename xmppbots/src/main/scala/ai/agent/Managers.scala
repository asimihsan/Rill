package ai.agent

import akka.actor.ActorRef
import akka.event.Logging
import akka.util.duration._
import akka.util.Timeout
import akka.dispatch.Await
import akka.dispatch.Future
import akka.pattern.ask
import akka.pattern.AskTimeoutException
import akka.actor.ActorSystem
import akka.actor.PoisonPill
import akka.actor.Props

sealed class ManagerMessage
case class ManagerUpdateServices() extends ManagerMessage
case class ManagerUpdateServicesResponse(services: List[Service]) extends ManagerMessage
case class ManagerLaunchBots() extends ManagerMessage

case class XMPPAgentManager(agents: ActorRef*)
    extends AgentManager(agents: _*)
    with akka.actor.ActorLogging {

    // -----------------------------------------------------------------------
    //  Set up local variables.
    // -----------------------------------------------------------------------
    var services: List[Service] = List()
    var bots: List[ActorRef] = List()
    var getServicesFailureCount = 0
    val MAXIMUM_UPDATE_SERVICES_FAILURE_COUNT = 3
    // -----------------------------------------------------------------------
    
    log.info("starting.")

    override def preStart = {
        log.debug("preStart entry.")
        ActorSystem("XMPPBot").scheduler.scheduleOnce(3 seconds) {
            self ! ManagerUpdateServices()
        }
    }

    override def postStop = {
        log.debug("postStop entry.")
    }

    def handleUpdateServicesFailure = {
        getServicesFailureCount += 1
        if (getServicesFailureCount < MAXIMUM_UPDATE_SERVICES_FAILURE_COUNT) {
            log.warning("No services available after requesting them. Try again soon.")
            ActorSystem("XMPPBot").scheduler.scheduleOnce(10 seconds) {
                self ! ManagerUpdateServices()
            }
        } else {
            log.error("Failed to get services too often.")
            self ! akka.actor.PoisonPill
        }
    }

    override def receive = {
        // -------------------------------------------------------------------
        //  Using the services from the ServiceRegistry launch bots.
        //
        //  Launch the masspinger actor first, for which a binding must
        //  exist, then launch all the other bots afterwards. This allows
        //  all the bots to tell the masspinger to notify them on ping
        //  changes.
        // -------------------------------------------------------------------
        case ManagerLaunchBots() => {
            log.debug("ManagerLaunchBots message received.")
            if (!services.exists(_.parserName == "masspinger")) {
                log.error("Service registry does not have a binding for masspinger.")
                self ! PoisonPill
            }

            // First, masspinger
            var masspinger: Option[ActorRef] = None
            for (service <- services; if (service.parserName == "masspinger"))
                masspinger = Some(context.actorOf(Props(new MasspingerActor(service)), name = "%s".format(service.parserName)))

            // Then , all the bots.
            for (service <- services; if (service.parserName != "masspinger"))
                bots = context.actorOf(Props(new BotActor(service, masspinger.get)), name = "%s".format(service.parserName)) :: bots
            bots = bots reverse
            //log.debug("bot actors: %s".format(bots))
        }
        // -------------------------------------------------------------------
        
        case ManagerUpdateServicesResponse(services) => {
            log.debug("ManagerUpdateServicesResponse message received.")
            if (services.length == 0) {
                log.warning("There are no services right now.")
                handleUpdateServicesFailure
            } else {
                log.debug("There are some services available.")
                this.services = services
                getServicesFailureCount = 0
                self ! ManagerLaunchBots()
            }
        }

        // -------------------------------------------------------------------
        //  Get a list of services from the ServiceRegistry.
        // -------------------------------------------------------------------
        case ManagerUpdateServices() => {
            log.debug("ManagerUpdateServices message received.")
            ServiceRegistryActor.ping(
                context = context,
                onSuccessCallback = result => { log.debug("success, result: %s".format(result)) },
                onExceptionCallback = exception => { log.error("exception %s.".format(exception)) })

            ServiceRegistryActor.getServices(
                context = context,
                onSuccessCallback = result => {
                    log.debug("Received list of services from ServiceRegistry.")
                    self ! ManagerUpdateServicesResponse(result.services)
                },
                onExceptionCallback = exception => {
                    log.error("serviceRegistry hit an exception %s. Stack trace:\n%s".format(
                        exception,
                        Exceptions.stackTraceToString(exception)))
                handleUpdateServicesFailure
                })
        } // case ManagerUpdateServices
        // -------------------------------------------------------------------
    }// def receive

}


