package com.bracits.bitspay.pricing.common.controller;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class WelcomeControllerTest {

    @Test
    void welcomesWithServiceName() {
        var body = new WelcomeController("pricing-service", 8106).welcome();

        assertThat(body)
                .containsEntry("service", "pricing-service")
                .containsEntry("message", "Welcome to Bits Pay pricing-service")
                .containsEntry("port", 8106)
                .containsKey("version");
    }
}
