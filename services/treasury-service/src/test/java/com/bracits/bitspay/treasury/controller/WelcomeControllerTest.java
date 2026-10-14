package com.bracits.bitspay.treasury.controller;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class WelcomeControllerTest {

    @Test
    void welcomesWithServiceName() {
        var body = new WelcomeController("treasury-service", 8107).welcome();

        assertThat(body)
                .containsEntry("service", "treasury-service")
                .containsEntry("message", "Welcome to Bits Pay treasury-service")
                .containsEntry("port", 8107)
                .containsKey("version");
    }
}
