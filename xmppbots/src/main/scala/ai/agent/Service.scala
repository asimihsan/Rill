package ai.agent

case class Service(parserName: String, binding: String) extends Ordered[Service] {
    override def toString = "{Service: parserName: %s, binding: %s".format(parserName, binding)
    def compare(that: Service) = parserName compare that.parserName
}

