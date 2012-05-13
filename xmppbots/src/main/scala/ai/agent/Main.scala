package ai.agent

import akka.actor._

/**
 * XMPP Runner
 */
object Main{

  def main(args: Array[String]) {
    val system = ActorSystem("XMPPBot")
    //val scalex = system.actorOf(Props(new Scalex), name = "scalex")
    //val ls = system.actorOf(Props(new Ls), name = "ls")
    //val interpret = system.actorOf(Props(new Interpret), name = "interpret")

    val serviceRegistryURI = "http://mink.datcon.co.uk:10000"
    val serviceRegistry = system.actorOf(Props(new ServiceRegistryActor(serviceRegistryURI)),
                                         name = "serviceRegistry")

    implicit val config = new ArgsConfig(args)
    val manager = system.actorOf(Props(new XMPPAgentManager(serviceRegistry)), name = "manager")

    println("Press any key to stop.")
    Thread.sleep(60000)
    System.in.read()
    manager ! 'stop
  }

}
