package com.askdata.platform.permission;

import com.askdata.platform.audit.AuditLogService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class PermissionAdministrationService {
    private final JdbcTemplate jdbc;
    private final AuditLogService audit;

    public PermissionAdministrationService(JdbcTemplate jdbc, AuditLogService audit) {
        this.jdbc = jdbc;
        this.audit = audit;
    }

    @Transactional
    public long invalidate(long userId, String reason) {
        var oldVersion = jdbc.queryForObject("select permission_version from iam_user where id=? for update", Long.class, userId);
        var newVersion = oldVersion + 1;
        jdbc.update("update iam_user set permission_version=?,updated_at=current_timestamp where id=?", newVersion, userId);
        jdbc.update("insert into iam_permission_change_event(user_id,old_version,new_version,reason) values (?,?,?,?)",
                userId, oldVersion, newVersion, reason);
        audit.append(new AuditLogService.AuditEvent("permission-" + java.util.UUID.randomUUID(), userId, "system", "INVALIDATE_PERMISSION",
                "IAM_USER", String.valueOf(userId), "{\"version\":" + oldVersion + "}", "{\"version\":" + newVersion + "}", null, null, "SUCCEEDED", null));
        return newVersion;
    }
}
