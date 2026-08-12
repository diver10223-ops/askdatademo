package com.askdata.platform.asset;

import com.askdata.platform.audit.AuditLogService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
public class AssetManagementService {
    private final JdbcTemplate jdbc;
    private final AuditLogService audit;

    public AssetManagementService(JdbcTemplate jdbc, AuditLogService audit) {
        this.jdbc = jdbc;
        this.audit = audit;
    }

    @Transactional
    public MetricView createMetric(MetricCommand command, long actorId) {
        jdbc.update("insert into meta_metric(code,name,business_definition,calculation_expression,unit,aggregation_type,classification_level,detail_allowed,status) values (?,?,?,?,?,?,?,?, 'DRAFT')",
                command.code, command.name, command.businessDefinition, command.calculationExpression, command.unit,
                command.aggregationType, command.classificationLevel, command.detailAllowed);
        var metric = findMetric(command.code);
        audit.append(new AuditLogService.AuditEvent("asset-" + UUID.randomUUID(), actorId == 0 ? null : actorId, "user-" + actorId,
                "CREATE_METRIC", "META_METRIC", String.valueOf(metric.id), null,
                "{\"code\":\"" + command.code + "\",\"status\":\"DRAFT\"}", null, null, "SUCCEEDED", null));
        return metric;
    }

    public List<MetricView> listMetrics() {
        return jdbc.query("select id,code,name,unit,aggregation_type,classification_level,detail_allowed,status,version_no from meta_metric order by code",
                (rs, row) -> new MetricView(rs.getLong(1), rs.getString(2), rs.getString(3), rs.getString(4),
                        rs.getString(5), rs.getString(6), rs.getBoolean(7), rs.getString(8), rs.getInt(9)));
    }

    private MetricView findMetric(String code) {
        return jdbc.query("select id,code,name,unit,aggregation_type,classification_level,detail_allowed,status,version_no from meta_metric where code=?",
                (rs, row) -> new MetricView(rs.getLong(1), rs.getString(2), rs.getString(3), rs.getString(4),
                        rs.getString(5), rs.getString(6), rs.getBoolean(7), rs.getString(8), rs.getInt(9)), code).stream().findFirst().orElseThrow();
    }

    public record MetricCommand(String code, String name, String businessDefinition, String calculationExpression,
                                String unit, String aggregationType, String classificationLevel, boolean detailAllowed) {}
    public record MetricView(long id, String code, String name, String unit, String aggregationType,
                             String classificationLevel, boolean detailAllowed, String status, int versionNo) {}
}
