package com.askdata.platform.provider;

import com.askdata.platform.audit.AuditLogService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.OffsetDateTime;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;

@Service
public class ProviderManagementService {
    private final JdbcTemplate jdbc;
    private final AuditLogService audit;
    private final List<ProviderDiagnosticAdapter> adapters;

    public ProviderManagementService(JdbcTemplate jdbc, AuditLogService audit, List<ProviderDiagnosticAdapter> adapters) {
        this.jdbc=jdbc; this.audit=audit; this.adapters=adapters;
    }

    @Transactional
    public SecretView createSecret(SecretCommand command, long actorId) {
        require(command.code(),"秘密引用编码"); require(command.externalReference(),"外部秘密引用");
        validateExternalReference(command.externalReference());
        String fingerprint=fingerprint(command.providerType(),command.externalReference());
        jdbc.update("insert into ai_secret_ref(code,secret_type,provider_type,external_ref,key_version,fingerprint,status) values (?,?,?,?,?,?,'ACTIVE')",
                command.code(),command.secretType(),command.providerType(),command.externalReference(),command.keyVersion(),fingerprint);
        audit(actorId,"CREATE_SECRET_REFERENCE","SECRET_REFERENCE",command.code(),"{\"fingerprint\":\""+fingerprint+"\"}");
        return secret(command.code());
    }

    @Transactional
    public SecretView rotateSecret(String code, RotateSecretCommand command, long actorId) {
        var current=internalSecretByCode(code);
        if (!current.status().equals("ACTIVE")) throw new ProviderManagementException("秘密引用不是ACTIVE状态");
        require(command.externalReference(),"外部秘密引用");
        validateExternalReference(command.externalReference());
        String fingerprint=fingerprint(current.providerType(),command.externalReference());
        jdbc.update("update ai_secret_ref set external_ref=?,key_version=?,fingerprint=?,revision_no=revision_no+1,rotated_at=?,updated_at=? where id=?",
                command.externalReference(),command.keyVersion(),fingerprint,OffsetDateTime.now(),OffsetDateTime.now(),current.id());
        jdbc.update("insert into ai_secret_rotation_log(secret_ref_id,from_fingerprint,to_fingerprint,from_key_version,to_key_version,rotated_by) values (?,?,?,?,?,?)",
                current.id(),current.fingerprint(),fingerprint,current.keyVersion(),command.keyVersion(),nullableActor(actorId));
        disableDependents(current.id());
        audit(actorId,"ROTATE_SECRET_REFERENCE","SECRET_REFERENCE",code,"{\"fingerprint\":\""+fingerprint+"\"}");
        return secret(code);
    }

    @Transactional
    public SecretView revokeSecret(String code, long actorId) {
        var current=internalSecretByCode(code);
        jdbc.update("update ai_secret_ref set status='REVOKED',revision_no=revision_no+1,updated_at=? where id=?",OffsetDateTime.now(),current.id());
        disableDependents(current.id());
        audit(actorId,"REVOKE_SECRET_REFERENCE","SECRET_REFERENCE",code,"{\"status\":\"REVOKED\"}");
        return secret(code);
    }

    @Transactional
    public ModelView createModel(ModelCommand command, long actorId) {
        require(command.code(),"模型编码"); require(command.endpoint(),"模型地址");
        jdbc.update("insert into ai_model_profile(code,name,provider_type,endpoint,model_name,secret_ref_id,timeout_seconds,max_tokens,status) values (?,?,?,?,?,?,?,?,'DRAFT')",
                command.code(),command.name(),command.providerType(),command.endpoint(),command.modelName(),command.secretRefId(),command.timeoutSeconds(),command.maxTokens());
        var id=jdbc.queryForObject("select id from ai_model_profile where code=?",Long.class,command.code());
        if(command.capabilities()!=null) command.capabilities().stream().distinct().forEach(capability -> jdbc.update("insert into ai_model_capability(model_profile_id,capability,enabled) values (?,?,true)",id,capability));
        audit(actorId,"CREATE_MODEL_PROFILE","MODEL_PROFILE",command.code(),"{\"status\":\"DRAFT\"}");
        return model(command.code());
    }

    @Transactional
    public DataSourceView createDataSource(DataSourceCommand command, long actorId) {
        require(command.code(),"数据源编码"); require(command.endpoint(),"数据源地址");
        jdbc.update("insert into meta_data_source(code,name,source_type,environment,endpoint,database_name,username,credential_secret_id,tls_enabled,read_only,max_rows,timeout_seconds,status) values (?,?,?,?,?,?,?,?,?,true,?,?,'DRAFT')",
                command.code(),command.name(),command.sourceType(),command.environment(),command.endpoint(),command.databaseName(),command.username(),command.secretRefId(),command.tlsEnabled(),command.maxRows(),command.timeoutSeconds());
        audit(actorId,"CREATE_DATA_SOURCE","DATA_SOURCE",command.code(),"{\"status\":\"DRAFT\"}");
        return dataSource(command.code());
    }

    @Transactional
    public DiagnosticView diagnoseModel(String code, long actorId) {
        var target=internalModel(code); var secret=activeSecret(target.secretRefId());
        var result=adapter(target.providerType()).diagnoseModel(new ProviderDiagnosticAdapter.ModelProbe(target.endpoint(),target.modelName(),target.timeoutSeconds()),secret.externalReference());
        var view=saveDiagnostic("MODEL_PROFILE",target.id(),target.version(),target.providerType(),result,actorId);
        audit(actorId,"DIAGNOSE_MODEL_PROFILE","MODEL_PROFILE",code,"{\"result\":\""+view.result()+"\",\"resultCode\":\""+view.resultCode()+"\"}");
        return view;
    }

    @Transactional
    public DiagnosticView diagnoseDataSource(String code, long actorId) {
        var target=internalDataSource(code); var secret=activeSecret(target.secretRefId());
        var result=adapter(secret.providerType()).diagnoseDataSource(new ProviderDiagnosticAdapter.DataSourceProbe(target.endpoint(),target.databaseName(),target.username(),target.timeoutSeconds()),secret.externalReference());
        var view=saveDiagnostic("DATA_SOURCE",target.id(),target.version(),secret.providerType(),result,actorId);
        audit(actorId,"DIAGNOSE_DATA_SOURCE","DATA_SOURCE",code,"{\"result\":\""+view.result()+"\",\"resultCode\":\""+view.resultCode()+"\"}");
        return view;
    }

    @Transactional public ModelView enableModel(String code,long actorId){var target=internalModel(code);activeSecret(target.secretRefId());requireSuccessfulDiagnostic("MODEL_PROFILE",target.id(),target.version());jdbc.update("update ai_model_profile set status='ENABLED',last_diagnostic_status='SUCCEEDED',updated_at=? where id=?",OffsetDateTime.now(),target.id());audit(actorId,"ENABLE_MODEL_PROFILE","MODEL_PROFILE",code,"{\"status\":\"ENABLED\"}");return model(code);}
    @Transactional public DataSourceView enableDataSource(String code,long actorId){var target=internalDataSource(code);activeSecret(target.secretRefId());requireSuccessfulDiagnostic("DATA_SOURCE",target.id(),target.version());jdbc.update("update meta_data_source set status='ENABLED',last_diagnostic_status='SUCCEEDED',updated_at=? where id=?",OffsetDateTime.now(),target.id());audit(actorId,"ENABLE_DATA_SOURCE","DATA_SOURCE",code,"{\"status\":\"ENABLED\"}");return dataSource(code);}

    @Transactional
    public RuntimeView createRuntime(RuntimeCommand command,long actorId){
        jdbc.update("insert into ai_runtime_profile(code,name,model_profile_id,data_source_id,execution_mode,status) values (?,?,?,?,?,'DRAFT')",command.code(),command.name(),command.modelProfileId(),command.dataSourceId(),command.executionMode());
        audit(actorId,"CREATE_RUNTIME_PROFILE","RUNTIME_PROFILE",command.code(),"{\"status\":\"DRAFT\"}"); return runtime(command.code());
    }
    @Transactional
    public RuntimeView enableRuntime(String code,long actorId){
        var view=runtime(code); Integer ready=jdbc.queryForObject("select count(*) from ai_runtime_profile r join ai_model_profile m on m.id=r.model_profile_id join meta_data_source d on d.id=r.data_source_id where r.id=? and m.status='ENABLED' and d.status='ENABLED'",Integer.class,view.id());
        if(ready==null||ready!=1)throw new ProviderManagementException("模型和数据源均诊断成功并启用后才能启用运行Profile");
        jdbc.update("update ai_runtime_profile set status='ENABLED',updated_at=? where id=?",OffsetDateTime.now(),view.id());audit(actorId,"ENABLE_RUNTIME_PROFILE","RUNTIME_PROFILE",code,"{\"status\":\"ENABLED\"}");return runtime(code);
    }

    public SecretView secret(String code){return jdbc.query("select id,code,secret_type,provider_type,key_version,fingerprint,status,revision_no from ai_secret_ref where code=?",(rs,n)->new SecretView(rs.getLong(1),rs.getString(2),rs.getString(3),rs.getString(4),rs.getString(5),rs.getString(6),rs.getString(7),rs.getInt(8)),code).stream().findFirst().orElseThrow(()->new ProviderManagementException("秘密引用不存在"));}
    public ModelView model(String code){return jdbc.query("select id,code,name,provider_type,endpoint,model_name,secret_ref_id,status,version_no from ai_model_profile where code=?",(rs,n)->new ModelView(rs.getLong(1),rs.getString(2),rs.getString(3),rs.getString(4),rs.getString(5),rs.getString(6),(Long)rs.getObject(7),rs.getString(8),rs.getInt(9)),code).stream().findFirst().orElseThrow(()->new ProviderManagementException("模型不存在"));}
    public DataSourceView dataSource(String code){return jdbc.query("select id,code,name,source_type,environment,endpoint,database_name,username,credential_secret_id,status,version_no from meta_data_source where code=?",(rs,n)->new DataSourceView(rs.getLong(1),rs.getString(2),rs.getString(3),rs.getString(4),rs.getString(5),rs.getString(6),rs.getString(7),rs.getString(8),(Long)rs.getObject(9),rs.getString(10),rs.getInt(11)),code).stream().findFirst().orElseThrow(()->new ProviderManagementException("数据源不存在"));}
    public RuntimeView runtime(String code){return jdbc.query("select id,code,name,model_profile_id,data_source_id,execution_mode,status,version_no from ai_runtime_profile where code=?",(rs,n)->new RuntimeView(rs.getLong(1),rs.getString(2),rs.getString(3),rs.getLong(4),rs.getLong(5),rs.getString(6),rs.getString(7),rs.getInt(8)),code).stream().findFirst().orElseThrow(()->new ProviderManagementException("运行Profile不存在"));}

    private DiagnosticView saveDiagnostic(String type,long id,int version,String provider,ProviderDiagnosticAdapter.DiagnosticResult result,long actor){String outcome=result.succeeded()?"SUCCEEDED":"FAILED";jdbc.update("insert into ai_provider_diagnostic(resource_type,resource_id,resource_version,provider_type,result,result_code,message,latency_ms,checked_by) values (?,?,?,?,?,?,?,?,?)",type,id,version,provider,outcome,result.code(),result.message(),result.latencyMs(),nullableActor(actor));if(type.equals("MODEL_PROFILE"))jdbc.update("update ai_model_profile set last_diagnostic_status=?,last_diagnostic_at=? where id=?",outcome,OffsetDateTime.now(),id);else jdbc.update("update meta_data_source set last_diagnostic_status=?,last_diagnostic_at=? where id=?",outcome,OffsetDateTime.now(),id);return new DiagnosticView(type,id,version,outcome,result.code(),result.message(),result.latencyMs());}
    private void requireSuccessfulDiagnostic(String type,long id,int version){Integer count=jdbc.queryForObject("select count(*) from ai_provider_diagnostic where resource_type=? and resource_id=? and resource_version=? and result='SUCCEEDED'",Integer.class,type,id,version);if(count==null||count==0)throw new ProviderManagementException("当前版本尚未通过Provider诊断");}
    private ProviderDiagnosticAdapter adapter(String type){return adapters.stream().filter(a->a.providerType().equalsIgnoreCase(type)).findFirst().orElseThrow(()->new ProviderManagementException("未配置Provider诊断适配器: "+type));}
    private InternalSecret activeSecret(Long id){if(id==null)throw new ProviderManagementException("未绑定秘密引用");var value=internalSecret(id);if(!value.status().equals("ACTIVE"))throw new ProviderManagementException("秘密引用不可用");return value;}
    private InternalSecret internalSecret(long id){return jdbc.query("select id,provider_type,external_ref,key_version,fingerprint,status from ai_secret_ref where id=?",(rs,n)->new InternalSecret(rs.getLong(1),rs.getString(2),rs.getString(3),rs.getString(4),rs.getString(5),rs.getString(6)),id).stream().findFirst().orElseThrow(()->new ProviderManagementException("秘密引用不存在"));}
    private InternalSecret internalSecretByCode(String code){return jdbc.query("select id,provider_type,external_ref,key_version,fingerprint,status from ai_secret_ref where code=?",(rs,n)->new InternalSecret(rs.getLong(1),rs.getString(2),rs.getString(3),rs.getString(4),rs.getString(5),rs.getString(6)),code).stream().findFirst().orElseThrow(()->new ProviderManagementException("秘密引用不存在"));}
    private InternalModel internalModel(String code){return jdbc.query("select id,provider_type,endpoint,model_name,secret_ref_id,timeout_seconds,version_no from ai_model_profile where code=?",(rs,n)->new InternalModel(rs.getLong(1),rs.getString(2),rs.getString(3),rs.getString(4),(Long)rs.getObject(5),rs.getDouble(6),rs.getInt(7)),code).stream().findFirst().orElseThrow(()->new ProviderManagementException("模型不存在"));}
    private InternalDataSource internalDataSource(String code){return jdbc.query("select id,source_type,endpoint,database_name,username,credential_secret_id,timeout_seconds,version_no from meta_data_source where code=?",(rs,n)->new InternalDataSource(rs.getLong(1),rs.getString(2),rs.getString(3),rs.getString(4),rs.getString(5),(Long)rs.getObject(6),rs.getDouble(7),rs.getInt(8)),code).stream().findFirst().orElseThrow(()->new ProviderManagementException("数据源不存在"));}
    private void disableDependents(long secretId){jdbc.update("update ai_model_profile set status='DISABLED',version_no=version_no+1,updated_at=? where secret_ref_id=? and status='ENABLED'",OffsetDateTime.now(),secretId);jdbc.update("update meta_data_source set status='DISABLED',version_no=version_no+1,updated_at=? where credential_secret_id=? and status='ENABLED'",OffsetDateTime.now(),secretId);jdbc.update("update ai_runtime_profile set status='DISABLED',version_no=version_no+1,updated_at=? where status='ENABLED' and (model_profile_id in (select id from ai_model_profile where secret_ref_id=?) or data_source_id in (select id from meta_data_source where credential_secret_id=?))",OffsetDateTime.now(),secretId,secretId);}
    private void audit(long actor,String action,String type,String id,String after){audit.append(new AuditLogService.AuditEvent("provider-"+UUID.randomUUID(),nullableActor(actor),"user-"+actor,action,type,id,null,after,null,null,"SUCCEEDED",null));}
    private Long nullableActor(long actor){return actor==0?null:actor;}
    private void require(String value,String label){if(value==null||value.isBlank())throw new ProviderManagementException(label+"不能为空");}
    private void validateExternalReference(String reference){if(!reference.matches("^(env|vault|kms|test-ref)://[^\\s]+$"))throw new ProviderManagementException("只允许保存env/vault/kms外部秘密引用，不允许提交秘密值");}
    private String fingerprint(String provider,String reference){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest((provider+":"+reference).getBytes(StandardCharsets.UTF_8)));}catch(Exception e){throw new IllegalStateException(e);}}

    private record InternalSecret(long id,String providerType,String externalReference,String keyVersion,String fingerprint,String status){}
    private record InternalModel(long id,String providerType,String endpoint,String modelName,Long secretRefId,double timeoutSeconds,int version){}
    private record InternalDataSource(long id,String sourceType,String endpoint,String databaseName,String username,Long secretRefId,double timeoutSeconds,int version){}
    public record SecretCommand(String code,String secretType,String providerType,String externalReference,String keyVersion){}
    public record RotateSecretCommand(String externalReference,String keyVersion){}
    public record ModelCommand(String code,String name,String providerType,String endpoint,String modelName,Long secretRefId,double timeoutSeconds,int maxTokens,List<String> capabilities){}
    public record DataSourceCommand(String code,String name,String sourceType,String environment,String endpoint,String databaseName,String username,Long secretRefId,boolean tlsEnabled,int maxRows,double timeoutSeconds){}
    public record RuntimeCommand(String code,String name,long modelProfileId,long dataSourceId,String executionMode){}
    public record SecretView(long id,String code,String secretType,String providerType,String keyVersion,String fingerprint,String status,int revision){}
    public record ModelView(long id,String code,String name,String providerType,String endpoint,String modelName,Long secretRefId,String status,int version){}
    public record DataSourceView(long id,String code,String name,String sourceType,String environment,String endpoint,String databaseName,String username,Long secretRefId,String status,int version){}
    public record RuntimeView(long id,String code,String name,long modelProfileId,long dataSourceId,String executionMode,String status,int version){}
    public record DiagnosticView(String resourceType,long resourceId,int resourceVersion,String result,String resultCode,String message,long latencyMs){}
}
