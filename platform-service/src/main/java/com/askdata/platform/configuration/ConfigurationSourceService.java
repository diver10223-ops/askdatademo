package com.askdata.platform.configuration;

import com.askdata.platform.audit.AuditLogService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.UUID;

@Service
public class ConfigurationSourceService {
    private final JdbcTemplate jdbc;
    private final AuditLogService audit;
    public ConfigurationSourceService(JdbcTemplate jdbc,AuditLogService audit){this.jdbc=jdbc;this.audit=audit;}

    public SourceState current(){return jdbc.query("select stage,write_source,legacy_read_enabled,legacy_write_enabled,disaster_seed_retained,version_no,updated_at from cfg_source_state where singleton_id=1",(rs,n)->new SourceState(rs.getString(1),rs.getString(2),rs.getBoolean(3),rs.getBoolean(4),rs.getBoolean(5),rs.getInt(6),rs.getObject(7,OffsetDateTime.class))).stream().findFirst().orElseThrow();}

    @Transactional
    public SourceState disableLegacyRead(long actorId){
        var before=current();
        if(before.stage().equals("DB_ONLY_SEED_STANDBY")) return before;
        if(!before.stage().equals("DB_PRIMARY_LEGACY_READ_ONLY")) throw new IllegalStateException("不支持的配置源切换状态");
        jdbc.update("update cfg_source_state set stage='DB_ONLY_SEED_STANDBY',legacy_read_enabled=false,version_no=version_no+1,updated_by=?,updated_at=? where singleton_id=1",actorId==0?null:actorId,OffsetDateTime.now());
        audit.append(new AuditLogService.AuditEvent("config-source-"+UUID.randomUUID(),actorId==0?null:actorId,"user-"+actorId,"DISABLE_LEGACY_CONFIG_READ","CONFIG_SOURCE","1","{\"stage\":\""+before.stage()+"\"}","{\"stage\":\"DB_ONLY_SEED_STANDBY\"}",null,null,"SUCCEEDED",null));
        return current();
    }

    public record SourceState(String stage,String writeSource,boolean legacyReadEnabled,boolean legacyWriteEnabled,boolean disasterSeedRetained,int version,OffsetDateTime updatedAt){}
}
