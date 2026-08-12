package com.askdata.platform.observability;

import com.askdata.platform.execution.ExecutionAdmissionController;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class AlertEvaluationService {
    private final JdbcTemplate jdbc;
    private final Map<String,AlertAdapter> adapters;
    private final String configuredAdapter;
    private final ExecutionAdmissionController admission;

    public AlertEvaluationService(JdbcTemplate jdbc, List<AlertAdapter> adapters,
                                  @Value("${askdata.observability.alert-adapter:logging}") String configuredAdapter,
                                  ExecutionAdmissionController admission) {
        this.jdbc=jdbc;this.adapters=adapters.stream().collect(java.util.stream.Collectors.toUnmodifiableMap(AlertAdapter::code,a->a));
        this.configuredAdapter=configuredAdapter;
        this.admission=admission;
    }

    @Scheduled(fixedDelayString="${askdata.observability.alert-evaluation-delay-ms:30000}")
    public void evaluate() {
        for (var rule : rules()) {
            var sample = sample(rule.metricCode());
            if (sample.count() < rule.minimumSamples() || !matches(rule.operator(),sample.value(),rule.threshold())) continue;
            var cutoff=OffsetDateTime.now().minusSeconds(rule.cooldownSeconds());
            if (count("select count(*) from ops_alert_event where rule_id=? and created_at>=?",rule.id(),cutoff)>0) continue;
            deliver(rule,sample);
        }
    }

    private void deliver(Rule rule, Sample sample) {
        var traceId="alert-"+UUID.randomUUID();
        var adapterCode=rule.adapterCode().equals("configured")?configuredAdapter:rule.adapterCode();
        jdbc.update("insert into ops_alert_event(rule_id,trace_id,metric_code,observed_value,sample_count,threshold_value,severity,delivery_adapter,delivery_status) values (?,?,?,?,?,?,?,?,'PENDING')",
                rule.id(),traceId,rule.metricCode(),sample.value(),sample.count(),rule.threshold(),rule.severity(),adapterCode);
        var eventId=jdbc.queryForObject("select max(id) from ops_alert_event where rule_id=? and trace_id=?",Long.class,rule.id(),traceId);
        try {
            var adapter=adapters.get(adapterCode);
            if(adapter==null)throw new IllegalStateException("ALERT_ADAPTER_NOT_CONFIGURED");
            adapter.send(new AlertAdapter.AlertNotification(traceId,rule.code(),rule.metricCode(),rule.severity(),sample.value(),rule.threshold(),sample.count()));
            jdbc.update("update ops_alert_event set delivery_status='DELIVERED',delivered_at=current_timestamp where id=?",eventId);
        } catch (RuntimeException exception) {
            jdbc.update("update ops_alert_event set delivery_status='DELIVERY_FAILED',delivery_error_code=? where id=?",
                    exception.getMessage()!=null&&exception.getMessage().equals("ALERT_ADAPTER_NOT_CONFIGURED")?"ADAPTER_NOT_CONFIGURED":"ADAPTER_DELIVERY_FAILED",eventId);
        }
    }

    private Sample sample(String metric) {
        return switch(metric) {
            case "execution.queue.depth" -> new Sample(admission.queueDepth(),1);
            case "execution.failure.ratio" -> ratio("run_request","status in ('FAILED','TIMED_OUT')","created_at");
            case "provider.failure.ratio" -> ratio("run_provider_execution","status='FAILED'","created_at");
            case "sql.failure.ratio" -> ratio("run_sql_execution","status='FAILED'","created_at");
            case "config.publish.failure.count" -> new Sample(number("select count(*) from audit_operation_log where action='PUBLISH_CONFIG' and result='FAILED' and created_at>=?",OffsetDateTime.now().minusMinutes(5)),
                    (int)number("select count(*) from audit_operation_log where action='PUBLISH_CONFIG' and created_at>=?",OffsetDateTime.now().minusMinutes(5)));
            default -> new Sample(0,0);
        };
    }
    private Sample ratio(String table,String failed,String timeColumn){
        var since=OffsetDateTime.now().minusMinutes(5);int total=(int)number("select count(*) from "+table+" where "+timeColumn+">=?",since);
        if(total==0)return new Sample(0,0);double failures=number("select count(*) from "+table+" where "+timeColumn+">=? and "+failed,since);
        return new Sample(failures/total,total);
    }
    private boolean matches(String operator,double value,double threshold){return switch(operator){case "GT"->value>threshold;case "GTE"->value>=threshold;case "LT"->value<threshold;case "LTE"->value<=threshold;default->false;};}
    private List<Rule> rules(){return jdbc.query("select id,code,metric_code,comparison_operator,threshold_value,minimum_samples,severity,cooldown_seconds,adapter_code from ops_alert_rule where enabled=true order by id",(rs,n)->new Rule(rs.getLong(1),rs.getString(2),rs.getString(3),rs.getString(4),rs.getDouble(5),rs.getInt(6),rs.getString(7),rs.getInt(8),rs.getString(9)));}
    private long count(String sql,Object...args){var value=jdbc.queryForObject(sql,Long.class,args);return value==null?0:value;}
    private double number(String sql,Object...args){var value=jdbc.queryForObject(sql,Number.class,args);return value==null?0:value.doubleValue();}
    private record Rule(long id,String code,String metricCode,String operator,double threshold,int minimumSamples,String severity,int cooldownSeconds,String adapterCode){}
    private record Sample(double value,int count){}
}
