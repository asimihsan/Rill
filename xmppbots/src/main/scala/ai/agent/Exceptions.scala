package ai.agent

object Exceptions {
    import java.io.{StringWriter, PrintWriter}
    def stackTraceToString(exception: Exception): String = {
        val sw = new StringWriter
        exception.printStackTrace(new PrintWriter(sw))
        sw.toString()
    }
}

