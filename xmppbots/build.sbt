fork in run := true

javaOptions in run ++= Seq("-server", 
                           "-Xmx2G",
                           "-Xss1M",
                           "-XX:+CMSClassUnloadingEnabled",
                           "-XX:MaxPermSize=384M",
                           "-XX:CompileThreshold=8000", 
                           "-XX:+UseConcMarkSweepGC",
                           "-verbose:gc",
                           "-XX:+PrintGCDetails",
                           "-XX:+PrintGCTimeStamps") 
