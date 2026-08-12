package com.askdata.platform;

import com.askdata.platform.approval.ApprovalService;
import com.askdata.platform.configuration.ConfigurationReleaseService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(properties = "spring.datasource.url=jdbc:h2:mem:approval-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1")
class ApprovalReleaseWorkflowTests {
    @Autowired JdbcTemplate jdbc;
    @Autowired ApprovalService approvals;
    @Autowired ConfigurationReleaseService releases;
    long applicant;
    long businessApprover;
    long securityApprover;

    @BeforeEach
    void setup() {
        jdbc.update("insert into iam_org(code,name,org_type,path,level_no,status) values ('org','Org','HEAD_OFFICE','/org',0,'ENABLED')");
        var org = jdbc.queryForObject("select id from iam_org where code='org'", Long.class);
        applicant = user("applicant", org); businessApprover = user("business", org); securityApprover = user("security", org);
        jdbc.update("insert into audit_workflow_definition(code,name,business_type,version_no,status,created_by) values ('cfg-publish','Config publish','CONFIG_PUBLISH',1,'ENABLED',?)", applicant);
        var workflow = jdbc.queryForObject("select id from audit_workflow_definition where code='cfg-publish'", Long.class);
        jdbc.update("insert into audit_workflow_step(workflow_id,step_no,name,approval_mode,approver_type,min_approvals) values (?,1,'Business','ANY','USER',1)", workflow);
        jdbc.update("insert into audit_workflow_step(workflow_id,step_no,name,approval_mode,approver_type,min_approvals) values (?,2,'Security','ANY','USER',1)", workflow);
    }

    @Test
    void draftApprovalPublishAndRollbackPreserveImmutableSnapshots() {
        var first = publish("v2-config-1", "{\"value\":1}");
        assertThat(releases.current("TEST").id()).isEqualTo(first);
        var second = publish("v2-config-2", "{\"value\":2}");
        assertThat(releases.current("TEST").id()).isEqualTo(second);
        var rollback = releases.rollback(first, securityApprover, "TEST");
        assertThat(rollback.id()).isNotEqualTo(first).isNotEqualTo(second);
        assertThat(rollback.snapshot()).isEqualTo("{\"value\":1}");
        assertThat(releases.current("TEST").id()).isEqualTo(rollback.id());
        assertThat(jdbc.queryForObject("select count(*) from audit_approval_action where action='APPROVE'", Integer.class)).isEqualTo(4);
        assertThat(jdbc.queryForObject("select count(*) from cfg_release", Integer.class)).isEqualTo(3);
    }

    private long publish(String releaseNo, String snapshot) {
        var release = releases.createDraft(releaseNo, releaseNo, snapshot, "test", applicant);
        releases.markReviewing(release, applicant);
        var approval = approvals.submit("CONFIG_PUBLISH", "Publish", applicant, "CFG_RELEASE", release, List.of(businessApprover));
        assertThat(approvals.approve(approval, businessApprover, "ok", List.of(securityApprover)).status()).isEqualTo("PENDING");
        assertThat(approvals.approve(approval, securityApprover, "ok", List.of()).status()).isEqualTo("APPROVED");
        releases.publish(release, approval, securityApprover, "TEST");
        return release;
    }

    private long user(String code, long org) {
        jdbc.update("insert into iam_user(public_id,username,display_name,user_type,org_id,identity_provider_code,external_subject,status) values (?,?,?,?,?,'test',?,'ENABLED')", code, code, code, "BUSINESS", org, code);
        return jdbc.queryForObject("select id from iam_user where public_id=?", Long.class, code);
    }
}
