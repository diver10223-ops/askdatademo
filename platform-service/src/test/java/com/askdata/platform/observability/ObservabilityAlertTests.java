package com.askdata.platform.observability;

import io.micrometer.core.instrument.MeterRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.annotation.Bean;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.client.RestClient;
import tools.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT,properties={
        "spring.datasource.url=jdbc:h2:mem:observability-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1",
        "spring.task.scheduling.enabled=false",
        "management.defaults.metrics.export.enabled=true",
        "management.prometheus.metrics.export.enabled=true",
        "management.endpoints.web.exposure.include=*",
        "askdata.observability.alert-adapter=test"
})
class ObservabilityAlertTests {
    @Autowired JdbcTemplate jdbc;
    @Autowired ObservabilityService observability;
    @Autowired AlertEvaluationService evaluator;
    @Autowired MeterRegistry meters;
    @Autowired ObjectMapper mapper;
    @Autowired RecordingAlertAdapter adapter;
    @LocalServerPort int port;

    @Test
    void exposesLowCardinalityMetricsAndAggregateSummaryWithoutSensitiveRuntimeData() throws Exception {
        var request=seedRequest("FAILED",0);
        var id=jdbc.queryForObject("select id from run_request where public_id=?",Long.class,request.toString());
        jdbc.update("insert into run_provider_execution(request_id,provider_kind,layer_code,provider,sequence_no,status,elapsed_ms,error_code) values (?,'MODEL','L2','provider-secret-name',1,'FAILED',12,'MODEL_ERROR')",id);
        jdbc.update("insert into run_sql_execution(request_id,sequence_no,business_sql,actual_sql_masked,parameters_json,source,status,elapsed_ms,error_code) values (?,1,'SELECT secret_business_column','SELECT ***','{\"password\":\"should-never-leak\"}','REAL_DATASOURCE','FAILED',8,'SQL_ERROR')",id);
        jdbc.update("insert into audit_operation_log(trace_id,actor_name_snapshot,action,resource_type,resource_id,result) values ('release-trace','operator','PUBLISH_CONFIG','CFG_RELEASE','1','FAILED')");

        var json=mapper.writeValueAsString(observability.summary());
        assertThat(json).contains("\"failed\":1", "\"averageElapsedMs\"");
        assertThat(json).doesNotContain("top-secret-question", "secret_business_column", "provider-secret-name", "should-never-leak", "SELECT ***");
        assertThat(jdbc.queryForObject("select r.trace_id from run_provider_execution p join run_request r on r.id=p.request_id where p.request_id=?",String.class,id)).isEqualTo("trace-"+request);
        assertThat(jdbc.queryForObject("select r.trace_id from run_sql_execution s join run_request r on r.id=s.request_id where s.request_id=?",String.class,id)).isEqualTo("trace-"+request);
        assertThat(meters.find("askdata.execution.requests").tag("status","FAILED").gauge()).isNotNull();
        assertThat(meters.find("askdata.provider.failures").tag("kind","MODEL").gauge()).isNotNull();
        assertThat(meters.find("askdata.sql.failures").gauge()).isNotNull();

        var prometheus=RestClient.create("http://127.0.0.1:"+port).get().uri("/actuator/prometheus").retrieve().body(String.class);
        assertThat(prometheus).contains("askdata_execution_requests", "status=\"FAILED\"");
        assertThat(prometheus).doesNotContain("top-secret-question", "secret_business_column", "should-never-leak");
    }

    @Test
    void persistsDeduplicatesAndDeliversAlertsThroughConfiguredAdapter() {
        adapter.notifications.clear();
        jdbc.update("update ops_alert_rule set threshold_value=0.40,minimum_samples=5,cooldown_seconds=300 where code='execution-failure-ratio'");
        seedRequest("FAILED",10);seedRequest("FAILED",11);seedRequest("FAILED",12);
        seedRequest("SUCCEEDED",13);seedRequest("SUCCEEDED",14);

        evaluator.evaluate();
        evaluator.evaluate();

        assertThat(adapter.notifications).hasSize(1);
        var notification=adapter.notifications.getFirst();
        assertThat(notification.ruleCode()).isEqualTo("execution-failure-ratio");
        assertThat(notification.metricCode()).isEqualTo("execution.failure.ratio");
        assertThat(notification.sampleCount()).isGreaterThanOrEqualTo(5);
        assertThat(jdbc.queryForObject("select count(*) from ops_alert_event where rule_id=(select id from ops_alert_rule where code='execution-failure-ratio')",Integer.class)).isEqualTo(1);
        assertThat(jdbc.queryForObject("select delivery_status from ops_alert_event where rule_id=(select id from ops_alert_rule where code='execution-failure-ratio')",String.class)).isEqualTo("DELIVERED");
        var stored=jdbc.queryForMap("select * from ops_alert_event where rule_id=(select id from ops_alert_rule where code='execution-failure-ratio')").toString();
        assertThat(stored).doesNotContain("top-secret-question", "SELECT", "password", "token");
    }

    private UUID seedRequest(String status,int discriminator) {
        var suffix=UUID.randomUUID().toString();
        jdbc.update("insert into iam_org(code,name,org_type,path,level_no,status) values (?,?,?,?,0,'ENABLED')","obs-org-"+suffix,"机构","HEAD_OFFICE","/"+suffix);
        var org=jdbc.queryForObject("select id from iam_org where code=?",Long.class,"obs-org-"+suffix);
        var userPublic=UUID.randomUUID();
        jdbc.update("insert into iam_user(public_id,username,display_name,user_type,org_id,identity_provider_code,external_subject,status) values (?,?,?,?,?,'test',?,'ENABLED')",userPublic.toString(),"obs-user-"+suffix,"用户","BUSINESS",org,userPublic.toString());
        var user=jdbc.queryForObject("select id from iam_user where public_id=?",Long.class,userPublic.toString());
        jdbc.update("insert into cfg_release(release_no,name,status,snapshot_json,snapshot_hash) values (?,?,'PUBLISHED','{}',?)","obs-release-"+suffix,"版本","a".repeat(64));
        var release=jdbc.queryForObject("select id from cfg_release where release_no=?",Long.class,"obs-release-"+suffix);
        var session=UUID.randomUUID();
        jdbc.update("insert into run_session(public_id,user_id,role_snapshot_json,permission_snapshot_json,permission_version,config_release_id,execution_mode) values (?,?,'[]','{}',1,?,'DEMO')",session.toString(),user,release);
        var sessionId=jdbc.queryForObject("select id from run_session where public_id=?",Long.class,session.toString());
        var request=UUID.randomUUID();
        jdbc.update("insert into run_request(public_id,session_id,user_id,trace_id,idempotency_key,question,mode,status) values (?,?,?,?,?,'top-secret-question','DEMO',?)",request.toString(),sessionId,user,"trace-"+request,"idem-"+discriminator+"-"+request,status);
        return request;
    }

    @TestConfiguration
    static class AlertTestConfiguration {
        @Bean RecordingAlertAdapter recordingAlertAdapter(){return new RecordingAlertAdapter();}
    }
    static class RecordingAlertAdapter implements AlertAdapter {
        final List<AlertNotification> notifications=new ArrayList<>();
        @Override public String code(){return "test";}
        @Override public void send(AlertNotification notification){notifications.add(notification);}
    }
}
