package com.bracits.bitspay.admin.common.controller;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class WelcomeControllerTest {

    @Test
    void welcomesWithServiceName() {
        var body = new WelcomeController("admin-service", 8115).welcome();

        assertThat(body)
                .containsEntry("service", "admin-service")
                .containsEntry("message", "Welcome to Bits Pay admin-service")
                .containsEntry("port", 8115)
                .containsKey("version");
    }
}
