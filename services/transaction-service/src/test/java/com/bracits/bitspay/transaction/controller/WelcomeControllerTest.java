package com.bracits.bitspay.transaction.controller;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class WelcomeControllerTest {

    @Test
    void welcomesWithServiceName() {
        var body = new WelcomeController("transaction-service", 8102).welcome();

        assertThat(body)
                .containsEntry("service", "transaction-service")
                .containsEntry("message", "Welcome to Bits Pay transaction-service")
                .containsEntry("port", 8102)
                .containsKey("version");
    }
}
