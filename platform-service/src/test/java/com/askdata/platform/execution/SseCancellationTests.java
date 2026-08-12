package com.askdata.platform.execution;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;

@SpringBootTest(properties={
        "spring.datasource.url=jdbc:h2:mem:sse-cancel-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1",
        "spring.task.scheduling.enabled=false"
})
class SseCancellationTests {
    @Autowired JdbcTemplate jdbc;
    @Autowired PlatformExecutionService service;
    @Autowired PlatformExecutionController controller;
    @Autowired ExecutionFactReconciler reconciler;
    @MockitoBean ExecutionClient client;

    @Test
    void resumesSseFromSharedDatabaseWithoutReplayingAcknowledgedEvents() throws Exception {
        var request = seedRequest("SUCCEEDED");
        var databaseId = jdbc.queryForObject("select id from run_request where public_id=?", Long.class, request.toString());
        var now = OffsetDateTime.now();
        jdbc.update("insert into run_sse_event(request_id,event_id,event_type,payload_json,created_at) values (?,?,?,?,?)",
                databaseId, 1L, "request.created", "{\"status\":\"PENDING\"}", now.minusSeconds(1));
        jdbc.update("insert into run_sse_event(request_id,event_id,event_type,payload_json,created_at) values (?,?,?,?,?)",
                databaseId, 2L, "request.completed", "{\"status\":\"SUCCEEDED\"}", now);

        var output = new ByteArrayOutputStream();
        controller.events(request, 1).writeTo(output);
        var stream = output.toString(StandardCharsets.UTF_8);

        assertThat(stream).startsWith("retry: 1000\n\n");
        assertThat(stream).contains("id: 2", "event: request.completed", "\"traceId\":\"trace-" + request + "\"");
        assertThat(stream).doesNotContain("id: 1", "event: request.created");
        verifyNoInteractions(client);
    }

    @Test
    void persistsCancellationBeforePropagationAndRetriesAFailedAttempt() {
        var request = seedRequest("RUNNING");
        when(client.cancel(request, "trace-" + request, "cancel-key-0001"))
                .thenThrow(new IllegalStateException("temporary outage"));

        assertThatThrownBy(() -> service.cancel(request, "operator-1", "cancel-key-0001"))
                .isInstanceOf(IllegalStateException.class);
        assertThat(jdbc.queryForMap("select status,cancel_requested,cancelled_by,cancel_attempts,cancel_propagated_at from run_request where public_id=?", request.toString()))
                .containsEntry("STATUS", "CANCELLATION_REQUESTED")
                .containsEntry("CANCEL_REQUESTED", true)
                .containsEntry("CANCELLED_BY", "operator-1")
                .containsEntry("CANCEL_ATTEMPTS", 1)
                .containsEntry("CANCEL_PROPAGATED_AT", null);

        reset(client);
        when(client.cancel(request, "trace-" + request, "cancel-" + request))
                .thenReturn(Map.of("requestId", request.toString(), "status", "CANCELLATION_REQUESTED"));
        when(client.state(request, "trace-" + request)).thenReturn(Map.of(
                "status", "CANCELLED", "lastLayer", "L4", "terminationReason", "CANCELLED",
                "result", Map.of("layers", java.util.List.of(), "sqlExecutions", java.util.List.of(),
                        "events", java.util.List.of(), "resultSnapshot", java.util.List.of(), "masked", true)));

        reconciler.reconcile();

        assertThat(jdbc.queryForObject("select status from run_request where public_id=?", String.class, request.toString()))
                .isEqualTo("CANCELLED");
        assertThat(jdbc.queryForObject("select cancel_attempts from run_request where public_id=?", Integer.class, request.toString()))
                .isEqualTo(2);
        assertThat(jdbc.queryForObject("select cancel_propagated_at from run_request where public_id=?", OffsetDateTime.class, request.toString()))
                .isNotNull();
        verify(client).cancel(request, "trace-" + request, "cancel-" + request);
        verify(client).state(request, "trace-" + request);
    }

    @Test
    void terminalCancellationIsIdempotentAndNeverCallsExecutionPlane() {
        var request = seedRequest("TIMED_OUT");
        var response = service.cancel(request, "operator-2", "cancel-key-0002");
        assertThat(response).containsEntry("status", "TIMED_OUT").containsEntry("idempotentReplay", true);
        assertThat(jdbc.queryForObject("select cancel_attempts from run_request where public_id=?", Integer.class, request.toString()))
                .isZero();
        verifyNoInteractions(client);
    }

    private UUID seedRequest(String status) {
        var suffix = UUID.randomUUID().toString();
        jdbc.update("insert into iam_org(code,name,org_type,path,level_no,status) values (?,?,?,?,0,'ENABLED')",
                "org-" + suffix, "测试机构", "HEAD_OFFICE", "/" + suffix);
        var org = jdbc.queryForObject("select id from iam_org where code=?", Long.class, "org-" + suffix);
        var userPublic = UUID.randomUUID();
        jdbc.update("insert into iam_user(public_id,username,display_name,user_type,org_id,identity_provider_code,external_subject,status) values (?,?,?,?,?,'test',?,'ENABLED')",
                userPublic.toString(), "user-" + suffix, "测试用户", "BUSINESS", org, userPublic.toString());
        var user = jdbc.queryForObject("select id from iam_user where public_id=?", Long.class, userPublic.toString());
        jdbc.update("insert into cfg_release(release_no,name,status,snapshot_json,snapshot_hash) values (?,?,'PUBLISHED','{}',?)",
                "release-" + suffix, "测试版本", "a".repeat(64));
        var release = jdbc.queryForObject("select id from cfg_release where release_no=?", Long.class, "release-" + suffix);
        var session = UUID.randomUUID();
        jdbc.update("insert into run_session(public_id,user_id,role_snapshot_json,permission_snapshot_json,permission_version,config_release_id,execution_mode) values (?,?,'[]','{}',1,?,'DEMO')",
                session.toString(), user, release);
        var sessionId = jdbc.queryForObject("select id from run_session where public_id=?", Long.class, session.toString());
        var request = UUID.randomUUID();
        jdbc.update("insert into run_request(public_id,session_id,user_id,trace_id,idempotency_key,question,mode,status) values (?,?,?,?,?,'q','DEMO',?)",
                request.toString(), sessionId, user, "trace-" + request, "idem-" + request, status);
        return request;
    }
}
