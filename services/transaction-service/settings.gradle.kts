// Standalone build (kernel K9): no include(), includeBuild(), ../ paths or mavenLocal().
pluginManagement {
    repositories { gradlePluginPortal(); mavenCentral() }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { mavenCentral() }
}

rootProject.name = "transaction-service"
