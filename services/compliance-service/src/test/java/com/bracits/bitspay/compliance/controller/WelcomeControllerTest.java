package com.bracits.bitspay.compliance.controller;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class WelcomeControllerTest {

    @Test
    void welcomesWithServiceName() {
        var body = new WelcomeController("compliance-service", 8111).welcome();

        assertThat(body)
                .containsEntry("service", "compliance-service")
                .containsEntry("message", "Welcome to Bits Pay compliance-service")
                .containsEntry("port", 8111)
                .containsKey("version");
    }
}
