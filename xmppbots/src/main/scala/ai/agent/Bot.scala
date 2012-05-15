package ai.agent

import akka.actor.ActorRef

case class Bot(service: Service, actorRef: ActorRef) {
    val parserName = service.parserName
    val binding = service.binding

    def server = "mink.datcon.co.uk"
    def conferenceServer = "conference.%s".format(server)
    def username = "%s@%s".format(parserName, server)
    def password = parserName
    def nickname = parserName
    
    override def toString = "{Bot: server=%s, username=%s, password=%s, nickname=%s}".format(
        server,username, password, nickname)
}

