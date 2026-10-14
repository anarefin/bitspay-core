package com.bracits.bitspay.admin;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;

/** Context loads and Flyway V1 runs against a real PostgreSQL 18 (Docker required). */
@Testcontainers
@SpringBootTest(properties = {"spring.flyway.create-schemas=true", "management.server.port=0", "server.port=0"})
class AdminServiceApplicationIT {

    @Container
    @ServiceConnection
    static PostgreSQLContainer postgres = new PostgreSQLContainer("postgres:18.6");

    @Test
    void contextLoads() {
    }
}
