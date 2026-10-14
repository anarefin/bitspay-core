package com.bracits.bitspay.limitsrisk.controller;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class WelcomeControllerTest {

    @Test
    void welcomesWithServiceName() {
        var body = new WelcomeController("limits-risk-service", 8105).welcome();

        assertThat(body)
                .containsEntry("service", "limits-risk-service")
                .containsEntry("message", "Welcome to Bits Pay limits-risk-service")
                .containsEntry("port", 8105)
                .containsKey("version");
    }
}
