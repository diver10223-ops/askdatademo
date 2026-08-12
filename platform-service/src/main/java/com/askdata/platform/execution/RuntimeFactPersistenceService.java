package com.askdata.platform.execution;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.OffsetDateTime;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class RuntimeFactPersistenceService {
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper=new ObjectMapper();
    public RuntimeFactPersistenceService(JdbcTemplate jdbc){this.jdbc=jdbc;}

    @Transactional
    public Map<String,Object> synchronize(UUID publicId,Map<String,Object> state){
        var requestId=jdbc.queryForObject("select id from run_request where public_id=?",Long.class,publicId.toString());
        jdbc.update("update run_request set status=?,last_layer=?,termination_reason=?,completed_at=case when ? in ('PENDING','RUNNING','CANCELLATION_REQUESTED') then completed_at else coalesce(completed_at,current_timestamp) end,synced_at=current_timestamp where id=?",
                text(state,"status"),text(state,"lastLayer"),text(state,"terminationReason"),text(state,"status"),requestId);
        var result=map(state.get("result"));
        int sequence=0;
        for(var layer:list(result.get("layers"))){sequence++;upsertLayer(requestId,sequence,layer);var provider=text(layer,"provider");var layerCode=text(layer,"layer_code");if(provider!=null&&("L2".equals(layerCode)||"L7".equals(layerCode)))upsertProvider(requestId,"MODEL",layerCode,provider,sequence,text(layer,"status"),number(layer,"elapsed_ms"),null,text(layer,"error_code"),false);}
        for(var sql:list(result.get("sqlExecutions"))){upsertSql(requestId,sql);var source=text(sql,"source");if(source!=null)upsertProvider(requestId,source.contains("FIXTURE")?"FIXTURE":"DATA_SOURCE","L6",source,integer(sql,"sequence"),text(sql,"status"),number(sql,"elapsed_ms"),longNumber(sql,"row_count"),text(sql,"error"),bool(sql,"fallback"));}
        for(var event:list(result.get("events")))upsertEvent(requestId,event);
        var snapshot=result.get("resultSnapshot");
        if(snapshot instanceof List<?> rows&&!rows.isEmpty())upsertResult(requestId,rows,bool(result,"masked"),text(result,"resultClassification"),text(result,"resultExpiresAt"));
        return state;
    }

    private void upsertLayer(long requestId,int sequence,Map<String,Object> row){
        var values=new Object[]{text(row,"status"),json(row.get("input")),json(row.get("output")),text(row,"provider"),number(row,"elapsed_ms"),text(row,"error_code"),requestId,sequence};
        int changed=jdbc.update("update run_layer_execution set status=?,input_json=?,output_json=?,provider=?,elapsed_ms=?,error_code=? where request_id=? and sequence_no=?",values);
        if(changed==0)jdbc.update("insert into run_layer_execution(request_id,sequence_no,layer_code,status,input_json,output_json,provider,elapsed_ms,error_code) values (?,?,?,?,?,?,?,?,?)",requestId,sequence,text(row,"layer_code"),text(row,"status"),json(row.get("input")),json(row.get("output")),text(row,"provider"),number(row,"elapsed_ms"),text(row,"error_code"));
    }
    private void upsertSql(long requestId,Map<String,Object> row){
        int sequence=integer(row,"sequence");var values=new Object[]{text(row,"business_sql"),text(row,"actual_sql"),json(row.get("parameters")),text(row,"source"),text(row,"status"),longNumber(row,"row_count"),number(row,"elapsed_ms"),text(row,"error"),bool(row,"fallback"),requestId,sequence};
        int changed=jdbc.update("update run_sql_execution set business_sql=?,actual_sql_masked=?,parameters_json=?,source=?,status=?,row_count=?,elapsed_ms=?,error_code=?,fallback=? where request_id=? and sequence_no=?",values);
        if(changed==0)jdbc.update("insert into run_sql_execution(request_id,sequence_no,business_sql,actual_sql_masked,parameters_json,source,status,row_count,elapsed_ms,error_code,fallback) values (?,?,?,?,?,?,?,?,?,?,?)",requestId,sequence,text(row,"business_sql"),text(row,"actual_sql"),json(row.get("parameters")),text(row,"source"),text(row,"status"),longNumber(row,"row_count"),number(row,"elapsed_ms"),text(row,"error"),bool(row,"fallback"));
    }
    private void upsertProvider(long requestId,String kind,String layer,String provider,int sequence,String status,Number elapsed,Long rows,String error,boolean fallback){
        int changed=jdbc.update("update run_provider_execution set provider=?,status=?,elapsed_ms=?,row_count=?,error_code=?,fallback=? where request_id=? and provider_kind=? and layer_code=? and sequence_no=?",provider,status,elapsed,rows,error,fallback,requestId,kind,layer,sequence);
        if(changed==0)jdbc.update("insert into run_provider_execution(request_id,provider_kind,layer_code,provider,sequence_no,status,elapsed_ms,row_count,error_code,fallback) values (?,?,?,?,?,?,?,?,?,?)",requestId,kind,layer,provider,sequence,status,elapsed,rows,error,fallback);
    }
    private void upsertEvent(long requestId,Map<String,Object> row){
        var eventId=longNumber(row,"event_id");int changed=jdbc.update("update run_sse_event set event_type=?,payload_json=?,created_at=? where request_id=? and event_id=?",text(row,"event_type"),json(row.get("payload")),OffsetDateTime.parse(text(row,"created_at")),requestId,eventId);
        if(changed==0)jdbc.update("insert into run_sse_event(request_id,event_id,event_type,payload_json,created_at) values (?,?,?,?,?)",requestId,eventId,text(row,"event_type"),json(row.get("payload")),OffsetDateTime.parse(text(row,"created_at")));
    }
    private void upsertResult(long requestId,List<?> rows,boolean masked,String classification,String expiresAt){
        var payload=json(rows);var level=classification==null?"INTERNAL":classification;var expiry=expiresAt==null?OffsetDateTime.now().plusDays(retention(level)):OffsetDateTime.parse(expiresAt);var hash=sha256(payload);
        int changed=jdbc.update("update run_result_snapshot set payload_json=?,masked=?,size_bytes=?,classification_level=?,content_hash=?,expires_at=? where request_id=?",payload,masked,payload.getBytes(StandardCharsets.UTF_8).length,level,hash,expiry,requestId);
        if(changed==0)jdbc.update("insert into run_result_snapshot(request_id,payload_json,masked,size_bytes,classification_level,content_hash,expires_at) values (?,?,?,?,?,?,?)",requestId,payload,masked,payload.getBytes(StandardCharsets.UTF_8).length,level,hash,expiry);
    }
    private int retention(String level){return switch(level){case "PUBLIC"->90;case "INTERNAL"->30;case "SENSITIVE"->7;default->1;};}
    @SuppressWarnings("unchecked") private Map<String,Object> map(Object value){return value instanceof Map<?,?>?(Map<String,Object>)value:Map.of();}
    private List<Map<String,Object>> list(Object value){return value instanceof List<?> items?items.stream().filter(Map.class::isInstance).map(this::map).toList():List.of();}
    private String text(Map<String,Object> row,String key){var value=row.get(key);return value==null?null:String.valueOf(value);}
    private int integer(Map<String,Object> row,String key){var value=row.get(key);return value instanceof Number n?n.intValue():Integer.parseInt(String.valueOf(value));}
    private Long longNumber(Map<String,Object> row,String key){var value=row.get(key);return value==null?null:(value instanceof Number n?n.longValue():Long.parseLong(String.valueOf(value)));}
    private Number number(Map<String,Object> row,String key){var value=row.get(key);return value instanceof Number n?n:null;}
    private boolean bool(Map<String,Object> row,String key){var value=row.get(key);return value instanceof Boolean b?b:value instanceof Number n&&n.intValue()!=0;}
    private String json(Object value){try{return mapper.writeValueAsString(value==null?Map.of():value);}catch(Exception e){throw new IllegalStateException("运行事实JSON无效",e);}}
    private String sha256(String value){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));}catch(Exception e){throw new IllegalStateException(e);}}
}
