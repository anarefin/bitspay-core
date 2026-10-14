package com.bracits.bitspay.disbursement.controller;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class WelcomeControllerTest {

    @Test
    void welcomesWithServiceName() {
        var body = new WelcomeController("disbursement-service", 8108).welcome();

        assertThat(body)
                .containsEntry("service", "disbursement-service")
                .containsEntry("message", "Welcome to Bits Pay disbursement-service")
                .containsEntry("port", 8108)
                .containsKey("version");
    }
}
