package com.bracits.bitspay.support.controller;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class WelcomeControllerTest {

    @Test
    void welcomesWithServiceName() {
        var body = new WelcomeController("support-service", 8109).welcome();

        assertThat(body)
                .containsEntry("service", "support-service")
                .containsEntry("message", "Welcome to Bits Pay support-service")
                .containsEntry("port", 8109)
                .containsKey("version");
    }
}
