package com.askdata.platform.configuration;

import com.askdata.platform.approval.ApprovalException;
import com.askdata.platform.approval.ApprovalService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.UUID;

@Service
public class ConfigurationReleaseService {
    private final JdbcTemplate jdbc;
    private final ApprovalService approvals;

    public ConfigurationReleaseService(JdbcTemplate jdbc, ApprovalService approvals) {
        this.jdbc = jdbc;
        this.approvals = approvals;
    }

    public long createDraft(String releaseNo, String name, String snapshot, String summary, long actorId) {
        jdbc.update("insert into cfg_release(release_no,name,status,snapshot_json,snapshot_hash,change_summary,created_by) values (?,?,'DRAFT',?,?,?,?)",
                releaseNo, name, snapshot, sha256(snapshot), summary, actorId);
        return jdbc.queryForObject("select id from cfg_release where release_no=?", Long.class, releaseNo);
    }

    @Transactional
    public void markReviewing(long releaseId) {
        var changed = jdbc.update("update cfg_release set status='REVIEWING' where id=? and status='DRAFT'", releaseId);
        if (changed != 1) throw new ApprovalException("仅草稿版本可进入审批");
    }

    @Transactional
    public PublishedRelease publish(long releaseId, long approvalId, long actorId, String environment) {
        if (!approvals.isApprovedFor(approvalId, "CFG_RELEASE", releaseId)) throw new ApprovalException("发布审批未通过或目标不匹配");
        var changed = jdbc.update("update cfg_release set status='PUBLISHED',published_by=?,published_at=current_timestamp where id=? and status='REVIEWING'", actorId, releaseId);
        if (changed != 1) throw new ApprovalException("发布版本状态无效");
        var current = jdbc.queryForList("select release_id from cfg_current_release where environment=?", Long.class, environment);
        if (current.isEmpty()) jdbc.update("insert into cfg_current_release(environment,release_id,updated_by) values (?,?,?)", environment, releaseId, actorId);
        else jdbc.update("update cfg_current_release set release_id=?,updated_by=?,updated_at=current_timestamp where environment=?", releaseId, actorId, environment);
        return get(releaseId);
    }

    @Transactional
    public PublishedRelease rollback(long targetReleaseId, long actorId, String environment) {
        var target = get(targetReleaseId);
        if (!target.status.equals("PUBLISHED") && !target.status.equals("ARCHIVED")) throw new ApprovalException("只能回滚到已发布快照");
        var releaseNo = "rollback-" + UUID.randomUUID();
        jdbc.update("insert into cfg_release(release_no,name,status,base_release_id,snapshot_json,snapshot_hash,change_summary,published_by,published_at,created_by) values (?,?, 'PUBLISHED',?,?,?,?,?,current_timestamp,?)",
                releaseNo, "回滚至 " + target.releaseNo, targetReleaseId, target.snapshot, target.snapshotHash, "受控回滚", actorId, actorId);
        var rollbackId = jdbc.queryForObject("select id from cfg_release where release_no=?", Long.class, releaseNo);
        jdbc.update("update cfg_current_release set release_id=?,updated_by=?,updated_at=current_timestamp where environment=?", rollbackId, actorId, environment);
        return get(rollbackId);
    }

    public PublishedRelease current(String environment) {
        var id = jdbc.queryForObject("select release_id from cfg_current_release where environment=?", Long.class, environment);
        return get(id);
    }
    private PublishedRelease get(long id) { return jdbc.query("select id,release_no,status,snapshot_json,snapshot_hash from cfg_release where id=?",(rs,row)->new PublishedRelease(rs.getLong(1),rs.getString(2),rs.getString(3),rs.getString(4),rs.getString(5)),id).stream().findFirst().orElseThrow(); }
    private String sha256(String value) { try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));}catch(Exception e){throw new IllegalStateException(e);} }
    public record PublishedRelease(long id, String releaseNo, String status, String snapshot, String snapshotHash) {}
}
