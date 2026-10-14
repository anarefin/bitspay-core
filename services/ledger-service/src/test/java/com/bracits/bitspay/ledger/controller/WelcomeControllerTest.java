package com.bracits.bitspay.ledger.controller;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class WelcomeControllerTest {

    @Test
    void welcomesWithServiceName() {
        var body = new WelcomeController("ledger-service", 8101).welcome();

        assertThat(body)
                .containsEntry("service", "ledger-service")
                .containsEntry("message", "Welcome to Bits Pay ledger-service")
                .containsEntry("port", 8101)
                .containsKey("version");
    }
}
