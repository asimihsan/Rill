import sbt._
import Keys._

object BuildSettings {
  val buildOrganization = "com.ai"
  val buildVersion      = "0.1"
  val buildScalaVersion = "2.9.2"

  val buildSettings = Defaults.defaultSettings ++ Seq (
    organization := buildOrganization,
    version      := buildVersion,
    scalaVersion := buildScalaVersion
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
  val http = "net.databinder" %% "dispatch-http" % "0.8.8"
  val json = "net.liftweb" % "lift-json_2.8.0" % "2.4"
}

object BuildSetup extends Build {
  import Resolvers._
  import Dependencies._
  import BuildSettings._

  val deps = Seq(
    smack,
    smackx,
    akka_actor,
    http,
    json
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
