package com.askdata.platform;

import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.sql.DriverManager;
import java.sql.SQLException;
import java.nio.file.Path;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DatabaseMigrationTests {
    @TempDir Path temporary;
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
    void multitaskTablesAndV20CompatibilityColumnsArePresent() throws Exception {
        var url = databaseUrl();
        Flyway.configure().dataSource(url, "sa", "").load().migrate();
        try (var connection = DriverManager.getConnection(url, "sa", "")) {
            var metadata = connection.getMetaData();
            try (var tables = metadata.getTables(null, null, "run_%", new String[]{"TABLE"})) {
                var names = new java.util.HashSet<String>();
                while (tables.next()) names.add(tables.getString("TABLE_NAME").toLowerCase());
                assertThat(names).contains("run_task_plan", "run_task_node", "run_task_dependency",
                        "run_task_attempt", "run_execution_fact", "run_answer_claim", "run_claim_evidence");
            }
            try (var columns = metadata.getColumns(null, null, "run_request", null)) {
                var names = new java.util.HashSet<String>();
                while (columns.next()) names.add(columns.getString("COLUMN_NAME").toLowerCase());
                assertThat(names).contains("current_plan_id", "plan_status", "total_tasks", "answer_version");
            }
        }
    }

    @Test
    void v16DatabaseUpgradesWithoutBackfillingHistoricalRequestGraph() throws Exception {
        var url = "jdbc:h2:file:" + temporary.resolve("v16-upgrade") + ";MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE";
        var v16 = Flyway.configure().dataSource(url, "sa", "").target("16").load();
        assertThat(v16.migrate().targetSchemaVersion).isEqualTo("16");
        try (var connection = DriverManager.getConnection(url, "sa", ""); var statement = connection.createStatement()) {
            statement.executeUpdate("insert into cfg_release(release_no,name,status,snapshot_json,snapshot_hash) values ('v16-test','V16','PUBLISHED','{}','" + "a".repeat(64) + "')");
            statement.executeUpdate("insert into iam_org(code,name,org_type,path,level_no,status) values ('V16-ORG','V16 Org','BRANCH','/V16-ORG',0,'ENABLED')");
            statement.executeUpdate("insert into iam_user(public_id,username,display_name,user_type,org_id,identity_provider_code,external_subject,status) select '00000000-0000-0000-0000-000000000016','v16-user','V16 User','BUSINESS',id,'LOCAL','v16-user','ENABLED' from iam_org where code='V16-ORG'");
            statement.executeUpdate("insert into run_session(public_id,user_id,role_snapshot_json,permission_snapshot_json,permission_version,config_release_id,execution_mode) select '10000000-0000-0000-0000-000000000016',u.id,'[]','{}',1,r.id,'DEMO' from iam_user u,cfg_release r where u.username='v16-user' and r.release_no='v16-test'");
            statement.executeUpdate("insert into run_request(public_id,session_id,user_id,trace_id,idempotency_key,question,mode,status) select '20000000-0000-0000-0000-000000000016',s.id,u.id,'v16-trace','v16-key','historical question','DEMO','SUCCEEDED' from run_session s join iam_user u on u.id=s.user_id where s.public_id='10000000-0000-0000-0000-000000000016'");
        }

        var latest = Flyway.configure().dataSource(url, "sa", "").load();
        assertThat(latest.migrate().migrationsExecuted).isEqualTo(1);
        try (var connection = DriverManager.getConnection(url, "sa", ""); var statement = connection.createStatement();
             var rows = statement.executeQuery("select status,current_plan_id,total_tasks from run_request where public_id='20000000-0000-0000-0000-000000000016'")) {
            assertThat(rows.next()).isTrue();
            assertThat(rows.getString("status")).isEqualTo("SUCCEEDED");
            assertThat(rows.getObject("current_plan_id")).isNull();
            assertThat(rows.getInt("total_tasks")).isZero();
        }
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
