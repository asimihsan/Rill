fork in run := true

javaOptions in run ++= Seq("-server",
                           "-Xms256m",
                           "-Xmx2G",
                           "-XX:+UseG1GC",
                           "-XX:+AggressiveOpts",
                           "-XX:+UseBiasedLocking",
                           "-XX:+UseFastAccessorMethods",
                           "-XX:+UseNUMA",
                           "-XX:+OptimizeStringConcat",
                           "-XX:+UseStringCache",
                           "-XX:+UseCompressedOops",
                           "-verbose:gc",
                           "-XX:+PrintGCTimeStamps",
                           "-XX:+PrintGCDetails")

