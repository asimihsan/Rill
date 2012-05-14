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

    //val scalex = system.actorOf(Props(new Scalex), name = "scalex")
    //val ls = system.actorOf(Props(new Ls), name = "ls")
    //val interpret = system.actorOf(Props(new Interpret), name = "interpret")

    val serviceRegistryURI = "http://mink.datcon.co.uk:10000"
    val serviceRegistry = system.actorOf(Props(new ServiceRegistryActor(serviceRegistryURI)),
                                         name = "serviceRegistry")

    implicit val config = new ArgsConfig(args)
    val manager = system.actorOf(Props(new XMPPAgentManager(serviceRegistry)), name = "manager")

    Thread.sleep(60000)
    System.in.read()
    manager ! 'stop

  } // def main
} // object Main
