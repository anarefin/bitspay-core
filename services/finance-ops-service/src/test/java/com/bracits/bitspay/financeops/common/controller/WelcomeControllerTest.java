package com.bracits.bitspay.financeops.common.controller;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class WelcomeControllerTest {

    @Test
    void welcomesWithServiceName() {
        var body = new WelcomeController("finance-ops-service", 8112).welcome();

        assertThat(body)
                .containsEntry("service", "finance-ops-service")
                .containsEntry("message", "Welcome to Bits Pay finance-ops-service")
                .containsEntry("port", 8112)
                .containsKey("version");
    }
}
