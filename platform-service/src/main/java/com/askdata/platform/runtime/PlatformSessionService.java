package com.askdata.platform.runtime;

import com.askdata.platform.permission.PermissionDecisionService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.ObjectMapper;

import java.util.UUID;

@Service
public class PlatformSessionService {
    private final JdbcTemplate jdbc;
    private final PermissionDecisionService permissions;
    private final ObjectMapper mapper = new ObjectMapper();

    public PlatformSessionService(JdbcTemplate jdbc, PermissionDecisionService permissions) { this.jdbc=jdbc; this.permissions=permissions; }

    @Transactional
    public SessionView create(long userId, String environment, String executionMode) {
        var releaseId=jdbc.queryForObject("select release_id from cfg_current_release where environment=?",Long.class,environment);
        var snapshot=permissions.snapshot(userId);
        var publicId=UUID.randomUUID().toString();
        try {
            jdbc.update("insert into run_session(public_id,user_id,role_snapshot_json,permission_snapshot_json,permission_version,config_release_id,execution_mode) values (?,?,?,?,?,?,?)",
                    publicId,userId,mapper.writeValueAsString(snapshot.roleCodes()),mapper.writeValueAsString(snapshot),snapshot.permissionVersion(),releaseId,executionMode);
        } catch(Exception exception){throw new IllegalStateException(exception);}
        return find(publicId);
    }
    public SessionView find(String publicId){return jdbc.query("select public_id,user_id,permission_version,config_release_id,execution_mode,active from run_session where public_id=?",(rs,row)->new SessionView(rs.getString(1),rs.getLong(2),rs.getLong(3),rs.getLong(4),rs.getString(5),rs.getBoolean(6)),publicId).stream().findFirst().orElseThrow();}
    public record SessionView(String id,long userId,long permissionVersion,long configReleaseId,String executionMode,boolean active){}
}
