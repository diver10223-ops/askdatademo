package com.askdata.platform;

import com.askdata.platform.permission.PermissionAdministrationService;
import com.askdata.platform.permission.PermissionDecisionService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import static com.askdata.platform.permission.PermissionDecisionService.ResourceType.METRIC;
import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(properties = "spring.datasource.url=jdbc:h2:mem:permission-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1")
class PermissionDecisionTests {
    @Autowired JdbcTemplate jdbc;
    @Autowired PermissionDecisionService decisions;
    @Autowired PermissionAdministrationService administration;
    long userId;
    long roleId;
    long metricId;

    @BeforeEach
    void setup() {
        jdbc.update("insert into iam_org(code,name,org_type,path,level_no,status) values ('org','Org','HEAD_OFFICE','/org',0,'ENABLED')");
        var orgId = jdbc.queryForObject("select id from iam_org where code='org'", Long.class);
        jdbc.update("insert into iam_user(public_id,username,display_name,user_type,org_id,identity_provider_code,external_subject,status) values ('user','user','User','BUSINESS',?,'test','user','ENABLED')", orgId);
        userId = jdbc.queryForObject("select id from iam_user where public_id='user'", Long.class);
        jdbc.update("insert into iam_role(code,name,role_type,status) values ('analyst','Analyst','BUSINESS','ENABLED')");
        roleId = jdbc.queryForObject("select id from iam_role where code='analyst'", Long.class);
        jdbc.update("insert into iam_user_role(user_id,role_id) values (?,?)", userId, roleId);
        jdbc.update("insert into meta_metric(code,name,business_definition,calculation_expression,unit,aggregation_type,classification_level,status) values ('loan','Loan','Loan','loan','元','SUM','INTERNAL','ENABLED')");
        metricId = jdbc.queryForObject("select id from meta_metric where code='loan'", Long.class);
    }

    @Test
    void deterministicPrecedenceAndPermissionVersionInvalidation() {
        assertThat(decisions.decide(userId, METRIC, metricId, "QUERY").reason()).isEqualTo("DEFAULT_DENY");
        jdbc.update("insert into iam_role_metric_scope(role_id,metric_id,detail_allowed,export_allowed,effect) values (?,?,false,false,'ALLOW')", roleId, metricId);
        assertThat(decisions.decide(userId, METRIC, metricId, "QUERY").reason()).isEqualTo("ROLE_ALLOW");
        jdbc.update("insert into iam_user_data_override(user_id,resource_type,resource_id,action_code,effect,reason) values (?,'METRIC',?,'QUERY','DENY','temporary deny')", userId, metricId);
        assertThat(decisions.decide(userId, METRIC, metricId, "QUERY").reason()).isEqualTo("USER_EXPLICIT_DENY");
        jdbc.update("update iam_user_data_override set effect='ALLOW' where user_id=?", userId);
        jdbc.update("update iam_role_metric_scope set effect='DENY' where role_id=?", roleId);
        assertThat(decisions.decide(userId, METRIC, metricId, "QUERY").reason()).isEqualTo("ROLE_DENY");
        jdbc.update("update iam_role_metric_scope set effect='ALLOW' where role_id=?", roleId);
        jdbc.update("insert into sec_mandatory_denial(resource_type,resource_id,action_code,reason_code,status) values ('METRIC',?,'QUERY','RESTRICTED','ENABLED')", metricId);
        assertThat(decisions.decide(userId, METRIC, metricId, "QUERY").reason()).isEqualTo("MANDATORY_COMPLIANCE_DENY");

        var oldVersion = decisions.snapshot(userId).permissionVersion();
        var newVersion = administration.invalidate(userId, "role changed");
        assertThat(newVersion).isEqualTo(oldVersion + 1);
        assertThat(decisions.snapshot(userId).permissionVersion()).isEqualTo(newVersion);
        assertThat(jdbc.queryForObject("select count(*) from iam_permission_change_event where user_id=?", Integer.class, userId)).isEqualTo(1);
    }
}
