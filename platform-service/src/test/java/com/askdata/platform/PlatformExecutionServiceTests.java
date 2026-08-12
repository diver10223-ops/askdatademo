package com.askdata.platform;

import com.askdata.platform.execution.ExecutionAccepted;
import com.askdata.platform.execution.ExecutionClient;
import com.askdata.platform.execution.ExecutionCommand;
import com.askdata.platform.execution.PlatformExecutionService;
import com.askdata.platform.runtime.PlatformSessionService;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@SpringBootTest(properties="spring.datasource.url=jdbc:h2:mem:execution-entry-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1")
class PlatformExecutionServiceTests {
    @Autowired JdbcTemplate jdbc;
    @Autowired PlatformSessionService sessions;
    @Autowired PlatformExecutionService service;
    @MockitoBean ExecutionClient client;

    @Test
    void javaEntryDerivesIdentitySnapshotsVersionAndTraceAndIsIdempotent()throws Exception{
        jdbc.update("insert into iam_org(code,name,org_type,path,level_no,status) values ('head','全行','HEAD_OFFICE','/head',0,'ENABLED')");
        var org=jdbc.queryForObject("select id from iam_org where code='head'",Long.class);
        jdbc.update("insert into iam_user(public_id,username,display_name,user_type,org_id,identity_provider_code,external_subject,status) values ('00000000-0000-4000-8000-000000000001','admin','管理员','ADMIN',?,'test','admin','ENABLED')",org);
        var user=jdbc.queryForObject("select id from iam_user where username='admin'",Long.class);
        jdbc.update("insert into iam_role(code,name,role_type,status) values ('admin','管理员','ADMIN','ENABLED')");
        var role=jdbc.queryForObject("select id from iam_role where code='admin'",Long.class);
        jdbc.update("insert into iam_user_role(user_id,role_id) values (?,?)",user,role);
        jdbc.update("insert into iam_role_org_scope(role_id,org_id,scope_type,effect) values (?,?,'EXACT','ALLOW')",role,org);
        var snapshot=Files.readString(Path.of("../fixtures/official_baseline_v1.json"));
        jdbc.update("insert into cfg_release(release_no,name,status,snapshot_json,snapshot_hash) values ('official-demo-baseline-v1','官方','PUBLISHED',?,?)",snapshot,"a".repeat(64));
        var release=jdbc.queryForObject("select id from cfg_release where release_no='official-demo-baseline-v1'",Long.class);
        jdbc.update("insert into cfg_current_release(environment,release_id) values ('TEST',?)",release);
        var session=sessions.create(user,"TEST","DEMO");
        when(client.submit(any(),eq("trace-p350"),eq("idem-p350-01"))).thenAnswer(invocation->{var command=(ExecutionCommand)invocation.getArgument(0);return new ExecutionAccepted(command.requestId(),ExecutionAccepted.Status.PENDING,"trace-p350",false);});

        var first=service.submit(new PlatformExecutionService.QueryCommand(session.id(),null,"2026年3月全行贷款投放是多少？",null,30000),"trace-p350","idem-p350-01");
        var capture=ArgumentCaptor.forClass(ExecutionCommand.class);verify(client).submit(capture.capture(),eq("trace-p350"),eq("idem-p350-01"));
        var sent=capture.getValue();
        assertThat(sent.subjectId()).isEqualTo("00000000-0000-4000-8000-000000000001");
        assertThat(sent.roleIds()).containsExactly("admin");
        assertThat(sent.permissionSnapshot()).containsEntry("permissionVersion",1);
        assertThat(sent.permissionSnapshot()).containsEntry("orgs",java.util.List.of("全行"));
        assertThat(sent.configVersionId()).isEqualTo("official-demo-baseline-v1");
        assertThat(sent.configSnapshot()).containsKeys("roles","scenarios","assets");
        assertThat(jdbc.queryForObject("select count(*) from run_request where public_id=? and trace_id=?",Integer.class,first.requestId().toString(),"trace-p350")).isEqualTo(1);
        var replay=service.submit(new PlatformExecutionService.QueryCommand(session.id(),null,"2026年3月全行贷款投放是多少？",null,30000),"different-trace","idem-p350-01");
        assertThat(replay.requestId()).isEqualTo(first.requestId());assertThat(replay.idempotentReplay()).isTrue();verifyNoMoreInteractions(client);
    }
}
