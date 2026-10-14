package com.bracits.bitspay.generalledger.controller;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class WelcomeControllerTest {

    @Test
    void welcomesWithServiceName() {
        var body = new WelcomeController("general-ledger-service", 8116).welcome();

        assertThat(body)
                .containsEntry("service", "general-ledger-service")
                .containsEntry("message", "Welcome to Bits Pay general-ledger-service")
                .containsEntry("port", 8116)
                .containsKey("version");
    }
}
