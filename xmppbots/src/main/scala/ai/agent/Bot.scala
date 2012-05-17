package ai.agent

import akka.actor.ActorRef

class Bot(service: Service, actorRef: ActorRef) extends Ordered[Bot] {
    val ref: ActorRef = actorRef
    val parserName = service.parserName
    val binding = service.binding
    def server = "mink.datcon.co.uk"
    def conferenceServer = "conference.%s".format(server)
    def username = "%s@%s".format(parserName, server)
    def password = parserName
    def nickname = parserName
    def hostname = parserName.split("_")(0)
    def botRef = ref
    
    override def toString = "{Bot: server=%s, username=%s, password=%s, nickname=%s}".format(
        server,username, password, nickname)
    def compare(that: Bot) = parserName compare that.parserName
}

