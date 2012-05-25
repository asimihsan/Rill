fork in run := true

javaOptions in run ++= Seq("-server",
                           "-Xms2g",
                           "-Xmx2g",
                           "-Xss256k",
                           "-Xmn1g",
                           "-XX:+UseG1GC",
                           "-XX:+AggressiveOpts",
                           "-XX:+UseBiasedLocking",
                           "-XX:+UseFastAccessorMethods",
                           "-XX:+UseNUMA",
                           "-XX:+CMSClassUnloadingEnabled",
                           "-XX:TargetSurvivorRatio=90",
                           "-XX:+OptimizeStringConcat",
                           "-XX:+UseStringCache",
                           "-XX:+UseCompressedOops",
                           "-verbose:gc",
                           "-XX:+PrintGCTimeStamps",
                           "-XX:+PrintGCDetails")

