import sbt._
import Keys._

object BuildSettings {
    val buildOrganization = "com.ai"
    val buildVersion      = "0.1"
    val buildScalaVersion = "2.9.2"
    val buildJavacOptions = Seq("-Xlint:all", "-deprecation")
    val buildScalacOptions = Seq("-unchecked", "-deprecation", "-optimise", "-explaintypes")

    val buildSettings = Defaults.defaultSettings ++ Seq (
        organization := buildOrganization,
        version      := buildVersion,
        scalaVersion := buildScalaVersion,
        javacOptions ++= buildJavacOptions,
        scalacOptions ++= buildScalacOptions
    )
}

object Resolvers {
    val akkaRepo = "Typesafe Repository" at "http://repo.typesafe.com/typesafe/releases/"
}

object Dependencies {
    val akka_version = "2.0.1"
    val smack = "org.igniterealtime.smack" % "smack" % "3.2.1"
    val smackx = "org.igniterealtime.smack" % "smackx" % "3.2.1"
    val akka_actor = "com.typesafe.akka" % "akka-actor" % akka_version
    val akka_slf4j = "com.typesafe.akka" % "akka-slf4j" % akka_version
    val akka_zeromq = "com.typesafe.akka" % "akka-zeromq" % akka_version
    val http = "net.databinder" %% "dispatch-http" % "0.8.8"
    val json = "net.liftweb" % "lift-json_2.8.0" % "2.4"
    val scalaj_http = "org.scalaj" %% "scalaj-http" % "0.3.1"
    val logback = "ch.qos.logback" % "logback-classic" % "1.0.3" % "runtime"
}

object BuildSetup extends Build {
  import Resolvers._
  import Dependencies._
  import BuildSettings._

  val deps = Seq(
    smack,
    smackx,
    akka_actor,
    akka_slf4j,
    akka_zeromq,
    http,
    json,
    scalaj_http,
    logback
  )

  val res = Seq(
    akkaRepo
  )

  lazy val project = Project(
    "scala-bot",
    file("."),
    settings = buildSettings ++ Seq(libraryDependencies ++= deps,
                                    resolvers := res)
  )
}
