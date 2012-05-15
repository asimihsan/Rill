package ai.agent

import org.jivesoftware.smackx.muc.MultiUserChat

case class Chat(bot: Bot, multiUserChat: MultiUserChat) {
    var filters: Set[String] = _

    def addFilter(filter: String) = filters += filter
    def removeFilter(filter: String) = filters = filters.filter(x => x != filter)
    def clearFilters = filters = Set()

    def room = multiUserChat getRoom

    override def toString = "{Chat. multiUserChat=%s, filters=%s}".format(multiUserChat, filters)
    override def hashCode = multiUserChat hashCode
    override def equals(that: Any): Boolean = that match {
        case other: Chat => multiUserChat == other.multiUserChat
        case _ => false
    }

} // class Chat


