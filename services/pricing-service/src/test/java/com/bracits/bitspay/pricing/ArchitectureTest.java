package com.bracits.bitspay.pricing;

import static com.tngtech.archunit.base.DescribedPredicate.not;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideInAPackage;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideInAnyPackage;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.Architectures.layeredArchitecture;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

/** Kernel K9 layering: controller -> service -> repository / client / messaging. */
@AnalyzeClasses(packages = "com.bracits.bitspay.pricing", importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureTest {

    @ArchTest
    static final ArchRule layers = layeredArchitecture()
            .consideringOnlyDependenciesInLayers()
            .withOptionalLayers(true)
            .layer("Controller").definedBy("..controller..")
            .layer("Service").definedBy("..service..")
            .layer("Repository").definedBy("..repository..")
            .layer("Client").definedBy("..client..")
            .layer("Messaging").definedBy("..messaging..")
            .layer("Config").definedBy("..config..")
            .whereLayer("Controller").mayNotBeAccessedByAnyLayer()
            .whereLayer("Service").mayOnlyBeAccessedByLayers("Controller", "Messaging", "Config")
            .whereLayer("Repository").mayOnlyBeAccessedByLayers("Service", "Messaging")
            .whereLayer("Client").mayOnlyBeAccessedByLayers("Service", "Config")
            .whereLayer("Messaging").mayOnlyBeAccessedByLayers("Service", "Config");

    @ArchTest
    static final ArchRule controllers_do_not_expose_entities = noClasses()
            .that().resideInAPackage("..controller..")
            .should().dependOnClassesThat().resideInAPackage("..entity..")
            .allowEmptyShould(true);

    @ArchTest
    static final ArchRule pricing_uses_only_campaign_facade = moduleUsesOnlyFacade("pricing", "campaign");

    @ArchTest
    static final ArchRule campaign_uses_only_pricing_facade = moduleUsesOnlyFacade("campaign", "pricing");

    /** Module `from` may use module `to` only through its `service` facade and `dto` packages. */
    private static ArchRule moduleUsesOnlyFacade(String from, String to) {
        String target = "com.bracits.bitspay.pricing." + to;
        return noClasses().that().resideInAPackage("com.bracits.bitspay.pricing." + from + "..")
                .should().dependOnClassesThat(resideInAPackage(target + "..")
                        .and(not(resideInAnyPackage(target + ".service..", target + ".dto.."))))
                .allowEmptyShould(true);
    }
}
