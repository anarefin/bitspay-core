package com.bracits.bitspay.admin.common.controller;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/** Skeleton smoke endpoint: GET /welcome (no actor headers needed). */
@RestController
public class WelcomeController {

    private final String service;
    private final int port;

    public WelcomeController(@Value("${spring.application.name}") String service,
                             @Value("${server.port:8115}") int port) {
        this.service = service;
        this.port = port;
    }

    @GetMapping(path = "/welcome", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> welcome() {
        String version = Optional.ofNullable(WelcomeController.class.getPackage().getImplementationVersion())
                .orElse("dev");
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("service", service);
        body.put("message", "Welcome to Bits Pay " + service);
        body.put("version", version);
        body.put("port", port);
        return body;
    }
}
