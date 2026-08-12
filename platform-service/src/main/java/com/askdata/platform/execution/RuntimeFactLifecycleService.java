package com.askdata.platform.execution;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.ObjectMapper;

import java.sql.Timestamp;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class RuntimeFactLifecycleService {
    private final JdbcTemplate jdbc;private final ObjectMapper mapper=new ObjectMapper();
    public RuntimeFactLifecycleService(JdbcTemplate jdbc){this.jdbc=jdbc;}
    @Transactional
    public LifecycleResult apply(OffsetDateTime now){
        int results=jdbc.update("delete from run_result_snapshot where expires_at<=?",now);
        int eventDays=days("RUN_SSE_EVENT");int events=jdbc.update("delete from run_sse_event where created_at<?",now.minusDays(eventDays));
        var archived=new LinkedHashMap<String,Integer>();
        archived.put("run_layer_execution",archive("run_layer_execution",days("RUN_LAYER_EXECUTION"),now));
        archived.put("run_sql_execution",archive("run_sql_execution",days("RUN_SQL_EXECUTION"),now));
        archived.put("run_provider_execution",archive("run_provider_execution",days("RUN_PROVIDER_EXECUTION"),now));
        archived.put("run_request",archiveRequests(days("RUN_REQUEST"),now));
        archived.put("run_session",archiveSessions(days("RUN_SESSION"),now));
        return new LifecycleResult(results,events,archived);
    }
    private int days(String fact){return jdbc.queryForObject("select online_days from ops_retention_policy where fact_type=? and enabled=true",Integer.class,fact);}
    private int archive(String table,int days,OffsetDateTime now){
        var rows=jdbc.queryForList("select f.*,r.public_id request_public_id from "+table+" f join run_request r on r.id=f.request_id where f.created_at<?",now.minusDays(days));int count=0;
        for(var row:rows){var id=String.valueOf(row.get("id"));jdbc.update("insert into run_fact_archive(source_table,source_id,request_public_id,payload_json,original_created_at) values (?,?,?,?,?)",table,id,row.get("request_public_id"),json(row),timestamp(row.get("created_at")));jdbc.update("delete from "+table+" where id=?",Long.parseLong(id));count++;}
        return count;
    }
    private int archiveRequests(int days,OffsetDateTime now){
        var rows=jdbc.queryForList("select r.* from run_request r where r.created_at<? and not exists(select 1 from run_layer_execution x where x.request_id=r.id) and not exists(select 1 from run_sql_execution x where x.request_id=r.id) and not exists(select 1 from run_provider_execution x where x.request_id=r.id) and not exists(select 1 from run_sse_event x where x.request_id=r.id) and not exists(select 1 from run_result_snapshot x where x.request_id=r.id)",now.minusDays(days));int count=0;
        for(var row:rows){var id=String.valueOf(row.get("id"));var publicId=String.valueOf(row.get("public_id"));jdbc.update("insert into run_fact_archive(source_table,source_id,request_public_id,payload_json,original_created_at) values ('run_request',?,?,?,?)",id,publicId,json(row),timestamp(row.get("created_at")));jdbc.update("delete from run_request where id=?",Long.parseLong(id));count++;}return count;
    }
    private int archiveSessions(int days,OffsetDateTime now){
        var rows=jdbc.queryForList("select s.* from run_session s where s.active=false and s.closed_at<? and not exists(select 1 from run_request r where r.session_id=s.id)",now.minusDays(days));int count=0;
        for(var row:rows){var id=String.valueOf(row.get("id"));jdbc.update("insert into run_fact_archive(source_table,source_id,payload_json,original_created_at) values ('run_session',?,?,?)",id,json(row),timestamp(row.get("created_at")));jdbc.update("delete from run_session where id=?",Long.parseLong(id));count++;}return count;
    }
    private OffsetDateTime timestamp(Object value){if(value instanceof OffsetDateTime time)return time;if(value instanceof Timestamp time)return time.toInstant().atOffset(java.time.ZoneOffset.UTC);return OffsetDateTime.parse(String.valueOf(value));}
    private String json(Map<String,Object> row){try{return mapper.writeValueAsString(row);}catch(Exception e){throw new IllegalStateException("归档事实无法序列化",e);}}
    public record LifecycleResult(int expiredResults,int expiredEvents,Map<String,Integer> archivedFacts){}
}
