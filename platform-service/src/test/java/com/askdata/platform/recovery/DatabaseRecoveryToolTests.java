package com.askdata.platform.recovery;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import javax.sql.DataSource;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(properties={
        "spring.datasource.url=jdbc:h2:mem:recovery-source;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1",
        "spring.task.scheduling.enabled=false"
})
class DatabaseRecoveryToolTests {
    @Autowired DataSource dataSource;
    @TempDir Path temporary;

    @Test
    void restoresMatchingSchemaAndInventoryAndRejectsNonEmptyTarget() throws Exception {
        String sourceUrl,user;
        try(var connection=dataSource.getConnection()){
            sourceUrl=connection.getMetaData().getURL();user=connection.getMetaData().getUserName();
            connection.createStatement().executeUpdate("insert into cfg_release(release_no,name,status,snapshot_json,snapshot_hash) values ('recovery-test','恢复测试','PUBLISHED','{\"v\":1}','"+"c".repeat(64)+"')");
            connection.createStatement().executeUpdate("insert into ai_secret_ref(code,secret_type,provider_type,external_ref,fingerprint,status) values ('recovery-ref','API_KEY','TEST','vault://recovery/ref','"+"d".repeat(64)+"','ACTIVE')");
        }
        var backup=temporary.resolve("database.zip");var before=temporary.resolve("before.properties");var after=temporary.resolve("after.properties");
        DatabaseRecoveryTool.backupH2(sourceUrl,user,"askdata-test-database-password",backup);
        DatabaseRecoveryTool.inventory(sourceUrl,user,"askdata-test-database-password",before,"h2");
        var targetUrl="jdbc:h2:mem:recovery-target;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1";
        DatabaseRecoveryTool.restoreH2(targetUrl,"sa","",backup);
        DatabaseRecoveryTool.inventory(targetUrl,"sa","",after,"h2");
        assertThat(Files.readString(after)).isEqualTo(Files.readString(before)).contains("flyway.version=17","release.count=1","secret.reference.count=1");
        assertThatThrownBy(()->DatabaseRecoveryTool.restoreH2(targetUrl,"sa","",backup))
                .isInstanceOf(IllegalStateException.class).hasMessageContaining("目标不是空库");
    }
}
