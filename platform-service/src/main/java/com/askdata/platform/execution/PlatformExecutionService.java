package com.askdata.platform.execution;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class PlatformExecutionService {
    private final JdbcTemplate jdbc;
    private final ExecutionClient client;
    private final RuntimeFactPersistenceService facts;
    private final ObjectMapper mapper=new ObjectMapper();
    public PlatformExecutionService(JdbcTemplate jdbc,ExecutionClient client,RuntimeFactPersistenceService facts){this.jdbc=jdbc;this.client=client;this.facts=facts;}

    @Transactional
    public ExecutionAccepted submit(QueryCommand query,String traceId,String idempotencyKey){
        if(idempotencyKey==null||idempotencyKey.length()<8)throw new IllegalArgumentException("Idempotency-Key至少8个字符");
        var session=jdbc.query("select s.id,s.public_id,s.user_id,s.role_snapshot_json,s.permission_snapshot_json,s.config_release_id,s.execution_mode,u.public_id,r.release_no,r.snapshot_json from run_session s join iam_user u on u.id=s.user_id join cfg_release r on r.id=s.config_release_id where s.public_id=? and s.active=true",
                (rs,n)->new SessionFacts(rs.getLong(1),rs.getString(2),rs.getLong(3),rs.getString(4),rs.getString(5),rs.getLong(6),rs.getString(7),rs.getString(8),rs.getString(9),rs.getString(10)),query.sessionId()).stream().findFirst().orElseThrow(()->new IllegalArgumentException("活动Session不存在"));
        var previous=jdbc.query("select public_id,trace_id from run_request where user_id=? and idempotency_key=?",(rs,n)->new ExistingRequest(rs.getString(1),rs.getString(2)),session.userId(),idempotencyKey).stream().findFirst();
        if(previous.isPresent())return new ExecutionAccepted(UUID.fromString(previous.get().publicId()),ExecutionAccepted.Status.PENDING,previous.get().traceId(),true);
        Long parentId=null; UUID parentPublicId=null;
        if(query.parentRequestId()!=null){var parent=jdbc.query("select r.id,r.public_id from run_request r where r.public_id=? and r.session_id=?",(rs,n)->new Parent(rs.getLong(1),rs.getString(2)),query.parentRequestId(),session.id()).stream().findFirst().orElseThrow(()->new IllegalArgumentException("父请求不属于当前Session"));parentId=parent.id();parentPublicId=UUID.fromString(parent.publicId());}
        Long scenarioId=null;
        if(query.scenarioId()!=null)scenarioId=jdbc.query("select id from flow_scenario where code=? and status='ENABLED'",(rs,n)->rs.getLong(1),query.scenarioId()).stream().findFirst().orElseThrow(()->new IllegalArgumentException("场景不存在或未启用"));
        var requestId=UUID.randomUUID();
        jdbc.update("insert into run_request(public_id,session_id,parent_request_id,user_id,trace_id,idempotency_key,scenario_id,question,mode,status) values (?,?,?,?,?,?,?,?,?,'PENDING')",requestId.toString(),session.id(),parentId,session.userId(),traceId,idempotencyKey,scenarioId,query.question(),session.mode());
        try{
            var command=new ExecutionCommand(requestId,UUID.fromString(session.publicId()),parentPublicId,session.subjectPublicId(),read(session.roleJson(),new TypeReference<List<String>>(){}),query.question(),query.scenarioId(),ExecutionCommand.ExecutionMode.valueOf(session.mode()),read(session.permissionJson(),new TypeReference<Map<String,Object>>(){}),session.releaseNo(),read(session.snapshotJson(),new TypeReference<Map<String,Object>>(){}),null,query.timeoutMs());
            return client.submit(command,traceId,idempotencyKey);
        }catch(RuntimeException exception){jdbc.update("update run_request set status='FAILED',termination_reason='EXECUTION_PLANE_UNAVAILABLE',completed_at=current_timestamp where public_id=?",requestId.toString());throw exception;}
    }

    public Map<String,Object> detail(UUID requestId,String traceId){return facts.synchronize(requestId,client.state(requestId,traceId));}

    private <T>T read(String json,TypeReference<T> type){try{return mapper.readValue(json,type);}catch(Exception exception){throw new IllegalStateException("Session或配置快照无效",exception);}}
    public record QueryCommand(String sessionId,String parentRequestId,String question,String scenarioId,int timeoutMs){public QueryCommand{if(question==null||question.isBlank())throw new IllegalArgumentException("问题不能为空");if(timeoutMs<1000||timeoutMs>300000)throw new IllegalArgumentException("超时必须在1000到300000毫秒之间");}}
    private record SessionFacts(long id,String publicId,long userId,String roleJson,String permissionJson,long releaseId,String mode,String subjectPublicId,String releaseNo,String snapshotJson){}
    private record ExistingRequest(String publicId,String traceId){}
    private record Parent(long id,String publicId){}
}
