package com.askdata.platform.api;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/v2")
public class PlatformHealthController {
    private final JdbcTemplate jdbc;
    private final String productVersion;

    public PlatformHealthController(JdbcTemplate jdbc, @Value("${info.app.version}") String productVersion) {
        this.jdbc = jdbc;
        this.productVersion = productVersion;
    }

    @GetMapping("/health")
    Map<String, Object> health() {
        var schemaVersion = jdbc.queryForObject(
                "select product_version from platform_schema_metadata order by id desc fetch first 1 row only",
                String.class
        );
        return Map.of("status", "ok", "version", productVersion, "schemaVersion", schemaVersion);
    }
}
