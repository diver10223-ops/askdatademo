package com.askdata.platform.identity;

import com.askdata.platform.audit.AuditLogService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.OffsetDateTime;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;

@Service
public class IdentityProvisioningService {
    private final JdbcTemplate jdbc;
    private final List<IdentityProviderAdapter> adapters;
    private final AuditLogService audit;
    private final ObjectMapper mapper = new ObjectMapper();

    public IdentityProvisioningService(JdbcTemplate jdbc, List<IdentityProviderAdapter> adapters, AuditLogService audit) {
        this.jdbc = jdbc;
        this.adapters = adapters;
        this.audit = audit;
    }

    @Transactional
    public ProvisionedIdentity authenticate(String providerCode, String credential, String clientIp, String userAgent) {
        var provider = jdbc.query("select id,provider_type,jit_provisioning,status from iam_identity_provider where code=?",
                (rs, row) -> new Provider(rs.getLong("id"), rs.getString("provider_type"), rs.getBoolean("jit_provisioning"), rs.getString("status")), providerCode)
                .stream().findFirst().orElseThrow(() -> new IdentityAuthenticationException("认证源不存在"));
        if (!provider.status.equals("ENABLED")) throw new IdentityAuthenticationException("认证源未启用");
        var adapter = adapters.stream().filter(item -> item.providerType().equals(provider.type)).findFirst()
                .orElseThrow(() -> new IdentityAuthenticationException("认证协议适配器不可用"));
        IdentityProviderAdapter.IdentityAssertion assertion;
        try {
            assertion = adapter.authenticate(credential);
        } catch (RuntimeException exception) {
            recordEvent(null, provider.id, hash(credential == null ? "" : credential), "FAILURE", "FAILED", clientIp, userAgent);
            throw exception;
        }
        var existing = jdbc.query("select ei.id,ei.user_id from iam_external_identity ei where ei.identity_provider_id=? and ei.external_subject=? and ei.status='ACTIVE'",
                (rs, row) -> new ExistingIdentity(rs.getLong("id"), rs.getLong("user_id")), provider.id, assertion.subject()).stream().findFirst();
        long userId;
        if (existing.isPresent()) {
            userId = existing.get().userId;
            jdbc.update("update iam_external_identity set external_username=?,attributes_hash=?,last_synced_at=?,last_authenticated_at=? where id=?",
                    assertion.username(), attributesHash(assertion), OffsetDateTime.now(), OffsetDateTime.now(), existing.get().id);
        } else {
            if (!provider.jit) throw new IdentityAuthenticationException("认证主体尚未同步且JIT已关闭");
            var orgId = jdbc.queryForObject("select id from iam_org where code=? and status='ENABLED'", Long.class, assertion.orgCode());
            var publicId = UUID.nameUUIDFromBytes((providerCode + ":" + assertion.subject()).getBytes(StandardCharsets.UTF_8)).toString();
            jdbc.update("insert into iam_user(public_id,username,display_name,user_type,org_id,identity_provider_code,external_subject,status) values (?,?,?,?,?,?,?,'ENABLED')",
                    publicId, assertion.username(), assertion.displayName(), "BUSINESS", orgId, providerCode, assertion.subject());
            userId = jdbc.queryForObject("select id from iam_user where public_id=?", Long.class, publicId);
            jdbc.update("insert into iam_external_identity(user_id,identity_provider_id,external_subject,external_username,attributes_hash,last_synced_at,last_authenticated_at,status) values (?,?,?,?,?,?,?,'ACTIVE')",
                    userId, provider.id, assertion.subject(), assertion.username(), attributesHash(assertion), OffsetDateTime.now(), OffsetDateTime.now());
        }
        recordEvent(userId, provider.id, hash(assertion.subject()), "LOGIN", "SUCCEEDED", clientIp, userAgent);
        audit.append(new AuditLogService.AuditEvent("auth-" + UUID.randomUUID(), userId, assertion.username(), "LOGIN",
                "IDENTITY_PROVIDER", providerCode, null, "{\"result\":\"SUCCEEDED\"}", clientIp, userAgent, "SUCCEEDED", null));
        return new ProvisionedIdentity(userId, assertion.subject(), assertion.username(), assertion.displayName(), assertion.orgCode());
    }

    private String attributesHash(IdentityProviderAdapter.IdentityAssertion assertion) {
        try { return hash(mapper.writeValueAsString(assertion.attributes())); }
        catch (Exception exception) { throw new IllegalStateException(exception); }
    }

    private void recordEvent(Long userId, long providerId, String subjectHash, String event, String result, String clientIp, String userAgent) {
        jdbc.update("insert into iam_user_auth_event(user_id,identity_provider_id,external_subject_hash,event_type,result,client_ip,user_agent_hash) values (?,?,?,?,?,?,?)",
                userId, providerId, subjectHash, event, result, clientIp, hash(userAgent == null ? "" : userAgent));
    }

    private String hash(String value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch (Exception exception) { throw new IllegalStateException(exception); }
    }

    private record Provider(long id, String type, boolean jit, String status) {}
    private record ExistingIdentity(long id, long userId) {}
    public record ProvisionedIdentity(long userId, String subject, String username, String displayName, String orgCode) {}
}
