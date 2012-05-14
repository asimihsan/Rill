package ai.agent

import akka.actor._
import akka.event.Logging

/**
 * XMPP Runner
 */
object Main {
  def main(args: Array[String]) {
    val system = ActorSystem("XMPPBot")
    system.log.info("XMPPBot is starting...")

    val serviceRegistryURI = "http://mink.datcon.co.uk:10000"
    val serviceRegistry = system.actorOf(Props(new ServiceRegistryActor(serviceRegistryURI)),
                                         name = "serviceRegistry")
    val manager = system.actorOf(Props(new XMPPAgentManager(serviceRegistry)), name = "manager")

  } // def main
} // object Main

