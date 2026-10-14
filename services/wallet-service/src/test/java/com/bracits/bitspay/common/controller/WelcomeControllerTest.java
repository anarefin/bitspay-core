package com.bracits.bitspay.common.controller;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class WelcomeControllerTest {

    @Test
    void welcomesWithServiceName() {
        var body = new WelcomeController("wallet-service", 8103).welcome();

        assertThat(body)
                .containsEntry("service", "wallet-service")
                .containsEntry("message", "Welcome to Bits Pay wallet-service")
                .containsEntry("port", 8103)
                .containsKey("version");
    }
}
