package com.bracits.bitspay.support;

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
@AnalyzeClasses(packages = "com.bracits.bitspay.support", importOptions = ImportOption.DoNotIncludeTests.class)
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
}
