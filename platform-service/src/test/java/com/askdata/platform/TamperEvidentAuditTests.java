package com.askdata.platform;

import com.askdata.platform.audit.AuditLogService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(properties = "spring.datasource.url=jdbc:h2:mem:audit-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1")
class TamperEvidentAuditTests {
    @Autowired AuditLogService audit;
    @Autowired JdbcTemplate jdbc;

    @Test
    void sensitiveValuesAreMaskedAndDatabaseTamperingIsDetected() {
        var categories = new String[]{"LOGIN", "GRANT_PERMISSION", "PUBLISH_CONFIG", "APPROVE", "ROTATE_SECRET", "SENSITIVE_ACCESS", "RESET_OPERATION"};
        long firstId = 0;
        for (var category : categories) {
            var id = audit.append(new AuditLogService.AuditEvent("trace-" + category, null, "tester", category,
                    "TEST", category, "{\"password\":\"before-secret\",\"safe\":1}",
                    "{\"apiKey\":\"after-secret\",\"safe\":2}", "127.0.0.1", "agent", "SUCCEEDED", null));
            if (firstId == 0) firstId = id;
        }
        assertThat(audit.verify()).isEqualTo(new AuditLogService.Verification(true, null, categories.length));
        var persisted = jdbc.queryForMap("select before_json,after_json from audit_operation_log where id=?", firstId);
        assertThat(persisted.toString()).contains("***").doesNotContain("before-secret", "after-secret");

        jdbc.update("update audit_operation_log set result='FAILED' where id=?", firstId);
        var broken = audit.verify();
        assertThat(broken.valid()).isFalse();
        assertThat(broken.firstBrokenLogId()).isEqualTo(firstId);
    }
}
