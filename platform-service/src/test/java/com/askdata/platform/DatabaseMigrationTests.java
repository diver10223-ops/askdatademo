package com.askdata.platform;

import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;

import java.sql.DriverManager;
import java.sql.SQLException;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DatabaseMigrationTests {
    private String databaseUrl() {
        return "jdbc:h2:mem:migration-" + UUID.randomUUID() + ";MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1";
    }

    @Test
    void emptyDatabaseMigratesAndRepeatedRunIsIdempotent() {
        var flyway = Flyway.configure().dataSource(databaseUrl(), "sa", "").load();
        var first = flyway.migrate();
        var second = flyway.migrate();
        assertThat(first.migrationsExecuted).isGreaterThan(0);
        assertThat(second.migrationsExecuted).isZero();
        assertThat(flyway.validateWithResult().validationSuccessful).isTrue();
    }

    @Test
    void applicationAccountCanUseGrantedTableButCannotCreateDdl() throws Exception {
        var url = databaseUrl().replace(";DB_CLOSE_DELAY=-1", "");
        try (var admin = DriverManager.getConnection(url, "sa", "")) {
            var flyway = Flyway.configure().dataSource(url, "sa", "").load();
            flyway.migrate();
            try (var statement = admin.createStatement()) {
            statement.execute("create user if not exists askdata_app password 'test-only'");
            statement.execute("grant select, insert, update, delete on platform_schema_metadata to askdata_app");
            }
            try (var app = DriverManager.getConnection(url, "askdata_app", "test-only"); var statement = app.createStatement()) {
                try (var rows = statement.executeQuery("select count(*) from platform_schema_metadata")) {
                    assertThat(rows.next()).isTrue();
                    assertThat(rows.getInt(1)).isEqualTo(1);
                }
                assertThatThrownBy(() -> statement.execute("create table forbidden_ddl(id bigint)"))
                        .isInstanceOf(SQLException.class);
            }
        }
    }
}
