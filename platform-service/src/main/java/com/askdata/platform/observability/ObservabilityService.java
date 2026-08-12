package com.askdata.platform.observability;

import com.askdata.platform.execution.ExecutionAdmissionController;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import jakarta.annotation.PostConstruct;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class ObservabilityService {
    private static final List<String> REQUEST_STATUSES = List.of("PENDING","RUNNING","WAITING_INPUT","SHORT_CIRCUITED",
            "BLOCKED","PARTIAL_SUCCESS","SUCCEEDED","FAILED","CANCELLATION_REQUESTED","CANCELLED","TIMED_OUT");
    private final JdbcTemplate jdbc;
    private final MeterRegistry meters;
    private final ExecutionAdmissionController admission;

    public ObservabilityService(JdbcTemplate jdbc, MeterRegistry meters, ExecutionAdmissionController admission) {
        this.jdbc = jdbc; this.meters = meters; this.admission = admission;
    }

    @PostConstruct
    void registerMetrics() {
        Gauge.builder("askdata.execution.active", admission, ExecutionAdmissionController::activeCount)
                .description("Currently admitted executions").register(meters);
        Gauge.builder("askdata.execution.queue.depth", admission, ExecutionAdmissionController::queueDepth)
                .description("Currently waiting executions").register(meters);
        for (var status : REQUEST_STATUSES) databaseGauge("askdata.execution.requests", "Execution requests by status",
                "status", status, "select count(*) from run_request where status=?", status);
        for (var kind : List.of("MODEL","DATA_SOURCE")) {
            databaseGauge("askdata.provider.executions", "Provider executions by kind", "kind", kind,
                    "select count(*) from run_provider_execution where provider_kind=?", kind);
            databaseGauge("askdata.provider.failures", "Failed provider executions by kind", "kind", kind,
                    "select count(*) from run_provider_execution where provider_kind=? and status='FAILED'", kind);
        }
        databaseGauge("askdata.sql.executions", "SQL executions", null, null,
                "select count(*) from run_sql_execution");
        databaseGauge("askdata.sql.failures", "Failed SQL executions", null, null,
                "select count(*) from run_sql_execution where status='FAILED'");
        databaseGauge("askdata.config.published", "Published configuration releases", null, null,
                "select count(*) from cfg_release where status='PUBLISHED'");
        databaseGauge("askdata.alerts.delivery_failed", "Failed alert deliveries", null, null,
                "select count(*) from ops_alert_event where delivery_status='DELIVERY_FAILED'");
    }

    public Summary summary() {
        var statuses = new LinkedHashMap<String,Long>();
        REQUEST_STATUSES.forEach(status -> statuses.put(status, count("select count(*) from run_request where status=?", status)));
        return new Summary(statuses,
                new QueueSummary(admission.activeCount(), admission.queueDepth(), number("select coalesce(avg(queue_wait_ms),0) from run_request")),
                executionSummary("run_provider_execution", "provider_kind='MODEL'"),
                executionSummary("run_provider_execution", "provider_kind='DATA_SOURCE'"),
                executionSummary("run_sql_execution", "1=1"),
                new ReleaseSummary(count("select count(*) from cfg_release where status='PUBLISHED'"),
                        count("select count(*) from audit_operation_log where action='PUBLISH_CONFIG' and result='FAILED'")),
                new TraceSummary(count("select count(*) from run_request where trace_id is null or trace_id=''"),
                        count("select count(*) from audit_operation_log where action in ('PUBLISH_CONFIG','ROLLBACK_CONFIG') and (trace_id is null or trace_id='')")),
                new AlertSummary(count("select count(*) from ops_alert_event"),
                        count("select count(*) from ops_alert_event where delivery_status='DELIVERY_FAILED'")));
    }

    private ExecutionSummary executionSummary(String table, String predicate) {
        return new ExecutionSummary(count("select count(*) from " + table + " where " + predicate),
                count("select count(*) from " + table + " where " + predicate + " and status='FAILED'"),
                number("select coalesce(avg(elapsed_ms),0) from " + table + " where " + predicate));
    }
    private void databaseGauge(String name,String description,String tag,String value,String sql,Object...args) {
        var builder=Gauge.builder(name, this, ignored -> number(sql,args)).description(description);
        if(tag!=null)builder.tag(tag,value);builder.register(meters);
    }
    private long count(String sql,Object...args) { var value=jdbc.queryForObject(sql,Long.class,args);return value==null?0:value; }
    private double number(String sql,Object...args) { try{var value=jdbc.queryForObject(sql,Number.class,args);return value==null?0:value.doubleValue();}catch(RuntimeException ignored){return 0;} }

    public record Summary(Map<String,Long> requests, QueueSummary queue, ExecutionSummary model,
                          ExecutionSummary dataSource, ExecutionSummary sql, ReleaseSummary releases,
                          TraceSummary missingTrace, AlertSummary alerts) {}
    public record QueueSummary(int active,int waiting,double averageWaitMs) {}
    public record ExecutionSummary(long total,long failed,double averageElapsedMs) {}
    public record ReleaseSummary(long published,long failedPublishAudits) {}
    public record TraceSummary(long requests,long releases) {}
    public record AlertSummary(long total,long deliveryFailed) {}
}
