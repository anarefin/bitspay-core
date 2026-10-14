// treasury-service — standalone Spring Boot build (kernel K9).
import org.springframework.boot.gradle.tasks.bundling.BootJar
import org.springframework.boot.gradle.tasks.run.BootRun

plugins {
    java
    jacoco
    alias(libs.plugins.spring.boot)
}

group = "com.bracits.bitspay"
version = "0.0.1-SNAPSHOT"
val javaVersion = libs.versions.java.get().toInt()
val svcName = rootProject.name

java { toolchain { languageVersion.set(JavaLanguageVersion.of(javaVersion)) } }

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
    options.release.set(javaVersion)
    options.compilerArgs.add("-parameters")
}

dependencies {
    implementation(platform(libs.spring.boot.bom))
    testImplementation(platform(libs.spring.boot.bom))
    implementation(libs.bundles.service.runtime)
    testImplementation(libs.bundles.service.test)
    testRuntimeOnly(libs.junit.platform.launcher)
}

// *Test = unit (task test); *IT = integration with Testcontainers (task integrationTest, Docker required)
tasks.named<Test>("test") {
    useJUnitPlatform()
    filter { includeTestsMatching("*Test"); isFailOnNoMatchingTests = false }
}
val integrationTest = tasks.register<Test>("integrationTest") {
    description = "Runs *IT integration tests (Testcontainers — Docker required)."
    group = LifecycleBasePlugin.VERIFICATION_GROUP
    testClassesDirs = sourceSets["test"].output.classesDirs
    classpath = sourceSets["test"].runtimeClasspath
    useJUnitPlatform { excludeEngines("archunit") }   // the ArchUnit engine ignores the class-name filter; rules run in `test`
    filter { includeTestsMatching("*IT"); isFailOnNoMatchingTests = false }
    shouldRunAfter(tasks.named("test"))
}

// Coverage: >= 90 % lines on **/service/** — business logic lives in the service layer (kernel K9)
jacoco { toolVersion = "0.8.14" }
tasks.named<JacocoCoverageVerification>("jacocoTestCoverageVerification") {
    executionData.setFrom(fileTree(layout.buildDirectory.dir("jacoco")).include("*.exec"))
    violationRules {
        rule {
            element = "PACKAGE"
            includes = listOf("*.service", "*.service.*")
            limit { counter = "LINE"; minimum = "0.90".toBigDecimal() }
        }
    }
    mustRunAfter(tasks.named("test"), integrationTest)
}
tasks.named("check") { dependsOn(integrationTest, tasks.named("jacocoTestCoverageVerification")) }

// Exactly one jar, build/libs/<service>.jar (copied into the image by docker/service.Dockerfile)
tasks.named<BootJar>("bootJar") { archiveFileName.set("$svcName.jar") }
tasks.named<Jar>("jar") { enabled = false }
tasks.named<BootRun>("bootRun") { systemProperty("spring.profiles.default", "local") }

// ---- Service-specific dependencies (libraries from gradle/libs.versions.toml only) ----
dependencies {
}
