package com.askdata.platform.permission;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.OffsetDateTime;

@Service
public class PermissionDecisionService {
    private final JdbcTemplate jdbc;

    public PermissionDecisionService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Decision decide(long userId, ResourceType resourceType, long resourceId, String actionCode) {
        if (exists("select count(*) from sec_mandatory_denial where resource_type=? and resource_id=? and action_code=? and status='ENABLED'",
                resourceType.name(), resourceId, actionCode)) {
            return new Decision(false, "MANDATORY_COMPLIANCE_DENY");
        }
        var userEffect = jdbc.query("select effect from iam_user_data_override where user_id=? and resource_type=? and resource_id=? and action_code=? and (valid_from is null or valid_from<=?) and (valid_to is null or valid_to>?)",
                (rs, row) -> rs.getString(1), userId, resourceType.name(), resourceId, actionCode, OffsetDateTime.now(), OffsetDateTime.now())
                .stream().findFirst();
        if (userEffect.filter("DENY"::equals).isPresent()) return new Decision(false, "USER_EXPLICIT_DENY");
        var roleEffect = roleEffect(userId, resourceType, resourceId, actionCode);
        if (roleEffect.deny) return new Decision(false, "ROLE_DENY");
        if (userEffect.filter("ALLOW"::equals).isPresent()) return new Decision(true, "USER_TEMPORARY_ALLOW");
        if (roleEffect.allow) return new Decision(true, "ROLE_ALLOW");
        return new Decision(false, "DEFAULT_DENY");
    }

    public PermissionSnapshot snapshot(long userId) {
        var version = jdbc.queryForObject("select permission_version from iam_user where id=?", Long.class, userId);
        var roles = jdbc.queryForList("select r.code from iam_role r join iam_user_role ur on ur.role_id=r.id where ur.user_id=? and r.status='ENABLED' and (ur.valid_from is null or ur.valid_from<=?) and (ur.valid_to is null or ur.valid_to>?) order by r.code",
                String.class, userId, OffsetDateTime.now(), OffsetDateTime.now());
        var orgs=effectiveNames(userId,ResourceType.ORG,"select distinct o.id,o.name from iam_org o join iam_role_org_scope s on s.org_id=o.id join iam_user_role ur on ur.role_id=s.role_id where ur.user_id=? and s.effect='ALLOW' and o.status='ENABLED'");
        var metrics=effectiveNames(userId,ResourceType.METRIC,"select distinct m.id,m.name from meta_metric m join iam_role_metric_scope s on s.metric_id=m.id join iam_user_role ur on ur.role_id=s.role_id where ur.user_id=? and s.effect='ALLOW' and m.status='ENABLED'");
        var tables=effectiveNames(userId,ResourceType.TABLE,"select distinct t.id,t.table_name from meta_data_table t join iam_role_table_scope s on s.table_id=t.id join iam_user_role ur on ur.role_id=s.role_id where ur.user_id=? and s.effect='ALLOW' and t.status='ENABLED'");
        var fields=effectiveNames(userId,ResourceType.FIELD,"select distinct f.id,f.field_name from meta_data_field f join iam_role_field_scope s on s.field_id=f.id join iam_user_role ur on ur.role_id=s.role_id where ur.user_id=? and s.effect='ALLOW' and f.status='ENABLED'");
        return new PermissionSnapshot(userId, version, roles,orgs,metrics,tables,fields);
    }

    private java.util.List<String> effectiveNames(long userId,ResourceType type,String sql){return jdbc.query(sql,(rs,n)->new NamedResource(rs.getLong(1),rs.getString(2)),userId).stream().filter(item->decide(userId,type,item.id(),"QUERY").allowed()).map(NamedResource::name).distinct().sorted().toList();}

    private Effects roleEffect(long userId, ResourceType type, long resourceId, String action) {
        var table = switch (type) {
            case ORG -> "iam_role_org_scope";
            case METRIC -> "iam_role_metric_scope";
            case TABLE -> "iam_role_table_scope";
            case FIELD -> "iam_role_field_scope";
            case FEATURE -> null;
        };
        if (table == null) return new Effects(false, false);
        var idColumn = type.name().toLowerCase() + "_id";
        var effects = jdbc.queryForList("select s.effect from " + table + " s join iam_user_role ur on ur.role_id=s.role_id where ur.user_id=? and s." + idColumn + "=? and (ur.valid_from is null or ur.valid_from<=?) and (ur.valid_to is null or ur.valid_to>?)",
                String.class, userId, resourceId, OffsetDateTime.now(), OffsetDateTime.now());
        return new Effects(effects.contains("ALLOW"), effects.contains("DENY"));
    }

    private boolean exists(String sql, Object... args) {
        return jdbc.queryForObject(sql, Integer.class, args) > 0;
    }

    public enum ResourceType { ORG, METRIC, TABLE, FIELD, FEATURE }
    public record Decision(boolean allowed, String reason) {}
    public record PermissionSnapshot(long userId, long permissionVersion, java.util.List<String> roleCodes,java.util.List<String> orgs,java.util.List<String> metrics,java.util.List<String> tables,java.util.List<String> fields) {}
    private record NamedResource(long id,String name){}
    private record Effects(boolean allow, boolean deny) {}
}
