package com.askdata.platform.approval;

import com.askdata.platform.audit.AuditLogService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

@Service
public class ApprovalService {
    private final JdbcTemplate jdbc;
    private final AuditLogService audit;

    public ApprovalService(JdbcTemplate jdbc, AuditLogService audit) {
        this.jdbc = jdbc;
        this.audit = audit;
    }

    @Transactional
    public long submit(String businessType, String title, long applicantId, String targetType, long targetId,
                       List<Long> firstStepApprovers) {
        var workflow = jdbc.query("select id,version_no from audit_workflow_definition where business_type=? and status='ENABLED' order by version_no desc fetch first 1 row only",
                (rs, row) -> new Workflow(rs.getLong("id"), rs.getInt("version_no")), businessType).stream().findFirst()
                .orElseThrow(() -> new ApprovalException("未配置启用的审批流程"));
        var firstStep = step(workflow.id, 1);
        if (firstStepApprovers.isEmpty()) throw new ApprovalException("首步审批人不能为空");
        var approvalNo = "APR-" + UUID.randomUUID();
        jdbc.update("insert into audit_approval(approval_no,approval_type,title,applicant_id,target_type,target_id,workflow_id,workflow_version,current_step_no,current_status,due_at) values (?,?,?,?,?,?,?,?,1,'PENDING',?)",
                approvalNo, businessType, title, applicantId, targetType, targetId, workflow.id, workflow.version,
                firstStep.timeoutHours == null ? null : OffsetDateTime.now().plusHours(firstStep.timeoutHours));
        var approvalId = jdbc.queryForObject("select id from audit_approval where approval_no=?", Long.class, approvalNo);
        firstStepApprovers.forEach(approver -> jdbc.update("insert into audit_approval_candidate(approval_id,step_no,approver_id,candidate_source,status) values (?,1,?,'SUBMITTED','PENDING')", approvalId, approver));
        jdbc.update("insert into audit_approval_action(approval_id,step_no,action,operator_id,opinion,from_status,to_status) values (?,1,'SUBMIT',?,'提交审批','DRAFT','PENDING')", approvalId, applicantId);
        audit.append(event(applicantId, "SUBMIT_APPROVAL", approvalId, "DRAFT", "PENDING"));
        return approvalId;
    }

    @Transactional
    public ApprovalResult approve(long approvalId, long operatorId, String opinion, List<Long> nextStepApprovers) {
        var approval = approval(approvalId);
        if (!approval.status.equals("PENDING")) throw new ApprovalException("审批实例不在待审批状态");
        var candidateCount = jdbc.queryForObject("select count(*) from audit_approval_candidate where approval_id=? and step_no=? and approver_id=? and status='PENDING'", Integer.class, approvalId, approval.stepNo, operatorId);
        if (candidateCount == 0) throw new ApprovalException("当前用户不是本步骤待审批人");
        jdbc.update("update audit_approval_candidate set status='APPROVED' where approval_id=? and step_no=? and approver_id=?", approvalId, approval.stepNo, operatorId);
        var currentStep = step(approval.workflowId, approval.stepNo);
        var approvedCount = jdbc.queryForObject("select count(*) from audit_approval_candidate where approval_id=? and step_no=? and status='APPROVED'", Integer.class, approvalId, approval.stepNo);
        var candidateTotal = jdbc.queryForObject("select count(*) from audit_approval_candidate where approval_id=? and step_no=?", Integer.class, approvalId, approval.stepNo);
        var stepComplete = currentStep.mode.equals("ANY") || approvedCount >= Math.max(currentStep.minApprovals, currentStep.mode.equals("ALL") ? candidateTotal : currentStep.minApprovals);
        var toStatus = "PENDING";
        if (stepComplete) {
            var next = optionalStep(approval.workflowId, approval.stepNo + 1);
            if (next == null) {
                toStatus = "APPROVED";
                jdbc.update("update audit_approval set current_status='APPROVED',completed_at=current_timestamp where id=?", approvalId);
                jdbc.update("update audit_approval_candidate set status='SKIPPED' where approval_id=? and step_no=? and status='PENDING'", approvalId, approval.stepNo);
            } else {
                if (nextStepApprovers.isEmpty()) throw new ApprovalException("下一步审批人不能为空");
                jdbc.update("update audit_approval set current_step_no=?,due_at=? where id=?", next.stepNo,
                        next.timeoutHours == null ? null : OffsetDateTime.now().plusHours(next.timeoutHours), approvalId);
                nextStepApprovers.forEach(approver -> jdbc.update("insert into audit_approval_candidate(approval_id,step_no,approver_id,candidate_source,status) values (?,?,?,'PREVIOUS_STEP','PENDING')", approvalId, next.stepNo, approver));
            }
        }
        jdbc.update("insert into audit_approval_action(approval_id,step_no,action,operator_id,opinion,from_status,to_status) values (?,?, 'APPROVE',?,?, 'PENDING',?)",
                approvalId, approval.stepNo, operatorId, opinion, toStatus);
        audit.append(event(operatorId, "APPROVE", approvalId, "PENDING", toStatus));
        return new ApprovalResult(approvalId, toStatus, stepComplete);
    }

    @Transactional
    public ApprovalResult reject(long approvalId, long operatorId, String opinion) {
        var approval = approval(approvalId);
        if (!approval.status.equals("PENDING")) throw new ApprovalException("审批实例不在待审批状态");
        var candidate = jdbc.queryForObject("select count(*) from audit_approval_candidate where approval_id=? and step_no=? and approver_id=? and status='PENDING'", Integer.class, approvalId, approval.stepNo, operatorId);
        if (candidate == 0) throw new ApprovalException("当前用户不是本步骤待审批人");
        jdbc.update("update audit_approval_candidate set status=case when approver_id=? then 'REJECTED' else 'SKIPPED' end where approval_id=? and step_no=? and status='PENDING'", operatorId, approvalId, approval.stepNo);
        jdbc.update("update audit_approval set current_status='REJECTED',completed_at=current_timestamp where id=?", approvalId);
        jdbc.update("insert into audit_approval_action(approval_id,step_no,action,operator_id,opinion,from_status,to_status) values (?,?,'REJECT',?,?,'PENDING','REJECTED')", approvalId, approval.stepNo, operatorId, opinion);
        audit.append(event(operatorId, "REJECT", approvalId, "PENDING", "REJECTED"));
        return new ApprovalResult(approvalId, "REJECTED", true);
    }

    public boolean isApprovedFor(long approvalId, String targetType, long targetId) {
        return jdbc.queryForObject("select count(*) from audit_approval where id=? and target_type=? and target_id=? and current_status='APPROVED'", Integer.class, approvalId, targetType, targetId) == 1;
    }

    private Approval approval(long id) {
        return jdbc.query("select workflow_id,current_step_no,current_status from audit_approval where id=? for update",
                (rs, row) -> new Approval(rs.getLong("workflow_id"), rs.getInt("current_step_no"), rs.getString("current_status")), id)
                .stream().findFirst().orElseThrow(() -> new ApprovalException("审批实例不存在"));
    }
    private Step step(long workflowId, int no) { var value=optionalStep(workflowId,no); if(value==null) throw new ApprovalException("审批步骤不存在"); return value; }
    private Step optionalStep(long workflowId, int no) { return jdbc.query("select step_no,approval_mode,min_approvals,timeout_hours from audit_workflow_step where workflow_id=? and step_no=?", (rs,row)->new Step(rs.getInt(1),rs.getString(2),rs.getInt(3),(Integer)rs.getObject(4)),workflowId,no).stream().findFirst().orElse(null); }
    private record Workflow(long id, int version) {}
    private record Approval(long workflowId, int stepNo, String status) {}
    private record Step(int stepNo, String mode, int minApprovals, Integer timeoutHours) {}
    private AuditLogService.AuditEvent event(long actorId, String action, long approvalId, String from, String to) {
        return new AuditLogService.AuditEvent("approval-" + UUID.randomUUID(), actorId, "user-" + actorId, action,
                "APPROVAL", String.valueOf(approvalId), "{\"status\":\"" + from + "\"}", "{\"status\":\"" + to + "\"}", null, null, "SUCCEEDED", null);
    }
    public record ApprovalResult(long approvalId, String status, boolean stepCompleted) {}
}
