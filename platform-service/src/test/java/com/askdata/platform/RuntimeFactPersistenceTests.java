package com.askdata.platform;

import com.askdata.platform.execution.RuntimeFactLifecycleService;
import com.askdata.platform.execution.RuntimeFactPersistenceService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(properties={"spring.datasource.url=jdbc:h2:mem:runtime-facts-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1","spring.task.scheduling.enabled=false"})
class RuntimeFactPersistenceTests {
    @Autowired JdbcTemplate jdbc;@Autowired RuntimeFactPersistenceService facts;@Autowired RuntimeFactLifecycleService lifecycle;

    @Test
    void synchronizesEveryRuntimeFactIdempotentlyAndAppliesRetention(){
        var request=seedRequest();var now=OffsetDateTime.now();
        var l2=new LinkedHashMap<String,Object>();l2.put("layer_code","L2");l2.put("status","SUCCEEDED");l2.put("input",Map.of("question","q"));l2.put("output",Map.of("parameters",Map.of("org","全行")));l2.put("provider","OPENAI_COMPATIBLE");l2.put("elapsed_ms",12.5);
        var l6=new LinkedHashMap<String,Object>();l6.put("layer_code","L6");l6.put("status","SUCCEEDED");l6.put("input",Map.of());l6.put("output",Map.of("row_count",1));l6.put("provider","ClickHouseProvider");l6.put("elapsed_ms",5.0);
        var sql=new LinkedHashMap<String,Object>();sql.put("sequence",1);sql.put("business_sql","SELECT business");sql.put("actual_sql","SELECT safe");sql.put("parameters",Map.of("org","全行"));sql.put("source","REAL_DATASOURCE");sql.put("status","SUCCEEDED");sql.put("row_count",1);sql.put("elapsed_ms",5.0);sql.put("fallback",false);
        var event=Map.<String,Object>of("event_id",1,"event_type","request.completed","payload",Map.of("status","SUCCEEDED"),"created_at",now.minusDays(31).toString());
        var result=new LinkedHashMap<String,Object>();result.put("layers",List.of(l2,l6));result.put("sqlExecutions",List.of(sql));result.put("events",List.of(event));result.put("resultSnapshot",List.of(Map.of("org_name","全行","current_value",100)));result.put("masked",true);result.put("resultClassification","SENSITIVE");
        var state=Map.<String,Object>of("status","SUCCEEDED","lastLayer","L7","result",result);
        facts.synchronize(request,state);facts.synchronize(request,state);
        var requestId=jdbc.queryForObject("select id from run_request where public_id=?",Long.class,request.toString());
        assertThat(jdbc.queryForObject("select status from run_request where id=?",String.class,requestId)).isEqualTo("SUCCEEDED");
        assertThat(jdbc.queryForObject("select count(*) from run_layer_execution where request_id=?",Integer.class,requestId)).isEqualTo(2);
        assertThat(jdbc.queryForObject("select count(*) from run_sql_execution where request_id=?",Integer.class,requestId)).isEqualTo(1);
        assertThat(jdbc.queryForObject("select count(*) from run_provider_execution where request_id=?",Integer.class,requestId)).isEqualTo(2);
        assertThat(jdbc.queryForObject("select count(*) from run_sse_event where request_id=?",Integer.class,requestId)).isEqualTo(1);
        assertThat(jdbc.queryForObject("select classification_level from run_result_snapshot where request_id=?",String.class,requestId)).isEqualTo("SENSITIVE");
        var expiry=jdbc.queryForObject("select expires_at from run_result_snapshot where request_id=?",OffsetDateTime.class,requestId);assertThat(expiry).isBetween(now.plusDays(6),now.plusDays(8));

        jdbc.update("update run_layer_execution set created_at=? where request_id=?",now.minusDays(181),requestId);
        jdbc.update("update run_sql_execution set created_at=? where request_id=?",now.minusDays(181),requestId);
        jdbc.update("update run_provider_execution set created_at=? where request_id=?",now.minusDays(181),requestId);
        jdbc.update("update run_request set created_at=? where id=?",now.minusDays(181),requestId);
        jdbc.update("update run_result_snapshot set expires_at=? where request_id=?",now.minusSeconds(1),requestId);
        var outcome=lifecycle.apply(now);
        assertThat(outcome.expiredResults()).isEqualTo(1);assertThat(outcome.expiredEvents()).isEqualTo(1);
        assertThat(outcome.archivedFacts()).containsEntry("run_layer_execution",2).containsEntry("run_sql_execution",1).containsEntry("run_provider_execution",2).containsEntry("run_request",1);
        assertThat(jdbc.queryForObject("select count(*) from run_fact_archive",Integer.class)).isEqualTo(6);
    }

    private UUID seedRequest(){
        jdbc.update("insert into iam_org(code,name,org_type,path,level_no,status) values ('runtime-head','全行','HEAD_OFFICE','/runtime-head',0,'ENABLED')");var org=jdbc.queryForObject("select id from iam_org where code='runtime-head'",Long.class);
        var userPublic=UUID.randomUUID();jdbc.update("insert into iam_user(public_id,username,display_name,user_type,org_id,identity_provider_code,external_subject,status) values (?,?,?,?,?,'test',?,'ENABLED')",userPublic.toString(),"runtime-user","运行用户","BUSINESS",org,userPublic.toString());var user=jdbc.queryForObject("select id from iam_user where public_id=?",Long.class,userPublic.toString());
        jdbc.update("insert into cfg_release(release_no,name,status,snapshot_json,snapshot_hash) values ('runtime-release','运行版本','PUBLISHED','{}',?)","a".repeat(64));var release=jdbc.queryForObject("select id from cfg_release where release_no='runtime-release'",Long.class);
        var session=UUID.randomUUID();jdbc.update("insert into run_session(public_id,user_id,role_snapshot_json,permission_snapshot_json,permission_version,config_release_id,execution_mode) values (?,?, '[]','{}',1,?,'DEMO')",session.toString(),user,release);var sessionId=jdbc.queryForObject("select id from run_session where public_id=?",Long.class,session.toString());
        var request=UUID.randomUUID();jdbc.update("insert into run_request(public_id,session_id,user_id,trace_id,idempotency_key,question,mode,status) values (?,?,?,?,?,'q','DEMO','PENDING')",request.toString(),sessionId,user,"trace-"+request,"idem-"+request);return request;
    }
}
