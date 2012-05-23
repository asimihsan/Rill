fork in run := true

javaOptions in run ++= Seq("-server",
                           "-Xmx2G",
                           "-Xss1M",
                           "-XX:+CMSClassUnloadingEnabled",
                           "-XX:+UnlockExperimentalVMOptions",
                           "-XX:+UseG1GC",
                           "-XX:MaxGCPauseMillis=10",
                           "-verbose:gc",
                           "-XX:+PrintGCDetails",
                           "-XX:+PrintGCTimeStamps") 
