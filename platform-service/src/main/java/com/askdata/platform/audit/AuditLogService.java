package com.askdata.platform.audit;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.node.ObjectNode;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.sql.Statement;
import java.time.OffsetDateTime;
import java.util.HexFormat;
import java.util.Iterator;
import java.util.Locale;
import java.util.Map;

@Service
public class AuditLogService {
    private static final String ZERO_HASH = "0".repeat(64);
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper = new ObjectMapper();

    public AuditLogService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Transactional
    public long append(AuditEvent event) {
        var before = maskJson(event.beforeJson);
        var after = maskJson(event.afterJson);
        var occurredAt = OffsetDateTime.now();
        var key = new GeneratedKeyHolder();
        jdbc.update(connection -> {
            var statement = connection.prepareStatement("insert into audit_operation_log(trace_id,actor_id,actor_name_snapshot,action,resource_type,resource_id,before_json,after_json,client_ip,user_agent_hash,result,error_code,created_at) values (?,?,?,?,?,?,?,?,?,?,?,?,?)", Statement.RETURN_GENERATED_KEYS);
            statement.setString(1, event.traceId); if (event.actorId == null) statement.setObject(2, null); else statement.setLong(2, event.actorId);
            statement.setString(3, event.actorName); statement.setString(4, event.action); statement.setString(5, event.resourceType);
            statement.setString(6, event.resourceId); statement.setString(7, before); statement.setString(8, after);
            statement.setString(9, event.clientIp); statement.setString(10, hash(event.userAgent == null ? "" : event.userAgent));
            statement.setString(11, event.result); statement.setString(12, event.errorCode); statement.setObject(13, occurredAt);
            return statement;
        }, key);
        var generatedId = key.getKeys().entrySet().stream()
                .filter(entry -> entry.getKey().equalsIgnoreCase("id"))
                .map(Map.Entry::getValue).findFirst()
                .orElseThrow(() -> new IllegalStateException("审计日志主键未返回"));
        var logId = ((Number) generatedId).longValue();
        var previous = jdbc.queryForObject("select last_hash from audit_chain_head where chain_name='operation' for update", String.class);
        var payloadHash = payloadHash(read(logId));
        var recordHash = hash(previous + payloadHash);
        jdbc.update("insert into audit_integrity_chain(audit_log_id,previous_hash,payload_hash,record_hash) values (?,?,?,?)", logId, previous, payloadHash, recordHash);
        jdbc.update("update audit_chain_head set last_log_id=?,last_hash=? where chain_name='operation'", logId, recordHash);
        return logId;
    }

    public Verification verify() {
        var previous = ZERO_HASH;
        var rows = jdbc.queryForList("select audit_log_id,previous_hash,payload_hash,record_hash from audit_integrity_chain order by audit_log_id");
        for (var chain : rows) {
            var id = ((Number) chain.get("audit_log_id")).longValue();
            var actualPayload = payloadHash(read(id));
            var expectedRecord = hash(previous + actualPayload);
            if (!previous.equals(chain.get("previous_hash")) || !actualPayload.equals(chain.get("payload_hash")) || !expectedRecord.equals(chain.get("record_hash"))) {
                return new Verification(false, id, rows.size());
            }
            previous = expectedRecord;
        }
        var head = jdbc.queryForObject("select last_hash from audit_chain_head where chain_name='operation'", String.class);
        return new Verification(previous.equals(head), previous.equals(head) ? null : (rows.isEmpty() ? null : ((Number) rows.get(rows.size()-1).get("audit_log_id")).longValue()), rows.size());
    }

    private StoredEvent read(long id) {
        return jdbc.query("select id,trace_id,actor_id,actor_name_snapshot,action,resource_type,resource_id,before_json,after_json,client_ip,user_agent_hash,result,error_code,created_at from audit_operation_log where id=?",
                (rs, row) -> new StoredEvent(rs.getLong("id"), rs.getString("trace_id"), (Long) rs.getObject("actor_id"), rs.getString("actor_name_snapshot"),
                        rs.getString("action"), rs.getString("resource_type"), rs.getString("resource_id"), rs.getString("before_json"), rs.getString("after_json"),
                        rs.getString("client_ip"), rs.getString("user_agent_hash"), rs.getString("result"), rs.getString("error_code"), rs.getObject("created_at", OffsetDateTime.class)), id)
                .stream().findFirst().orElseThrow();
    }

    private String payloadHash(StoredEvent e) {
        return hash(String.join("\u001f", String.valueOf(e.id), safe(e.traceId), String.valueOf(e.actorId), safe(e.actorName), safe(e.action),
                safe(e.resourceType), safe(e.resourceId), safe(e.beforeJson), safe(e.afterJson), safe(e.clientIp), safe(e.userAgentHash),
                safe(e.result), safe(e.errorCode), String.valueOf(e.createdAt.toInstant().toEpochMilli())));
    }

    private String maskJson(String value) {
        if (value == null || value.isBlank()) return value;
        try { var node=mapper.readTree(value); mask(node); return mapper.writeValueAsString(node); }
        catch (Exception exception) { return "\"***INVALID_OR_SENSITIVE_PAYLOAD***\""; }
    }
    private void mask(JsonNode node) {
        if (node instanceof ObjectNode object) {
            Iterator<Map.Entry<String, JsonNode>> fields = object.properties().iterator();
            while (fields.hasNext()) { var field=fields.next(); if (isSensitive(field.getKey())) object.put(field.getKey(), "***"); else mask(field.getValue()); }
        } else if (node.isArray()) node.forEach(this::mask);
    }
    private boolean isSensitive(String key) { var k=key.toLowerCase(Locale.ROOT); return k.contains("password")||k.contains("secret")||k.contains("token")||k.contains("apikey")||k.contains("api_key")||k.contains("ciphertext")||k.contains("mobile")||k.contains("email"); }
    private String hash(String value) { try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));}catch(Exception e){throw new IllegalStateException(e);} }
    private String safe(String value) { return value == null ? "<null>" : value; }

    public record AuditEvent(String traceId, Long actorId, String actorName, String action, String resourceType,
                             String resourceId, String beforeJson, String afterJson, String clientIp,
                             String userAgent, String result, String errorCode) {}
    public record Verification(boolean valid, Long firstBrokenLogId, int checkedRecords) {}
    private record StoredEvent(long id, String traceId, Long actorId, String actorName, String action, String resourceType,
                               String resourceId, String beforeJson, String afterJson, String clientIp,
                               String userAgentHash, String result, String errorCode, OffsetDateTime createdAt) {}
}
