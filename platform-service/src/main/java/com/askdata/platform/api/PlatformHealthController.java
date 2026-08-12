package com.askdata.platform.api;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/v2")
public class PlatformHealthController {
    private final JdbcTemplate jdbc;

    public PlatformHealthController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @GetMapping("/health")
    Map<String, Object> health() {
        var schemaVersion = jdbc.queryForObject(
                "select product_version from platform_schema_metadata order by id desc fetch first 1 row only",
                String.class
        );
        return Map.of("status", "ok", "version", "2.0.0-SNAPSHOT", "schemaVersion", schemaVersion);
    }
}
