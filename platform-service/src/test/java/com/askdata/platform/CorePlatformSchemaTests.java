package com.askdata.platform;

import com.askdata.platform.secret.SecretReferenceRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import java.sql.SQLException;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest
class CorePlatformSchemaTests {
    @Autowired JdbcTemplate jdbc;
    @Autowired SecretReferenceRepository secrets;

    @Test
    void coreTablesAndIndexesExist() {
        var expected = Set.of("cfg_release", "ai_secret_ref", "audit_operation_log", "iam_org", "iam_user",
                "iam_role", "iam_permission", "meta_data_source", "meta_data_table", "meta_data_field",
                "meta_metric", "meta_dimension", "flow_scenario", "flow_parameter_rule", "flow_sql_template", "run_request");
        var actual = Set.copyOf(jdbc.queryForList("select table_name from information_schema.tables where table_schema='public'", String.class));
        assertThat(actual).containsAll(expected);
        var indexes = jdbc.queryForList("select index_name from information_schema.indexes where table_schema='public'", String.class);
        assertThat(indexes).contains("idx_run_request_session_created", "idx_audit_trace", "idx_iam_user_org_status");
    }

    @Test
    void uniqueForeignKeyAndStateConstraintsRejectInvalidData() {
        jdbc.update("insert into iam_org(code,name,org_type,path,level_no,status) values ('root','Root','HEAD_OFFICE','/root',0,'ENABLED')");
        assertThatThrownBy(() -> jdbc.update("insert into iam_org(code,name,org_type,path,level_no,status) values ('root','Duplicate','HEAD_OFFICE','/duplicate',0,'ENABLED')"))
                .hasRootCauseInstanceOf(SQLException.class);
        assertThatThrownBy(() -> jdbc.update("insert into iam_user(public_id,username,display_name,user_type,org_id,identity_provider_code,external_subject,status) values ('bad','bad','Bad','BUSINESS',999,'local','bad','ENABLED')"))
                .hasRootCauseInstanceOf(SQLException.class);
        assertThatThrownBy(() -> jdbc.update("insert into cfg_release(release_no,name,status,snapshot_json,snapshot_hash) values ('bad','Bad','INVALID','{}',?)", "0".repeat(64)))
                .hasRootCauseInstanceOf(SQLException.class);
    }

    @Test
    void secretRepositoryNeverReturnsExternalReference() {
        secrets.create("model-key", "MODEL_API_KEY", "ENV", "ASKDATA_MODEL_API_KEY", "a".repeat(64));
        var publicView = secrets.findPublicByCode("model-key").orElseThrow();
        assertThat(publicView.code()).isEqualTo("model-key");
        assertThat(publicView.toString()).doesNotContain("ASKDATA_MODEL_API_KEY");
        assertThat(publicView.getClass().getRecordComponents()).extracting(component -> component.getName())
                .doesNotContain("externalRef", "ciphertext", "value", "password");
    }
}
