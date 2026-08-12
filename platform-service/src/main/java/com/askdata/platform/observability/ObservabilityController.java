package com.askdata.platform.observability;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v2/admin/observability")
public class ObservabilityController {
    private final ObservabilityService service;
    private final JdbcTemplate jdbc;
    public ObservabilityController(ObservabilityService service,JdbcTemplate jdbc){this.service=service;this.jdbc=jdbc;}

    @GetMapping("/summary")
    ObservabilityService.Summary summary(){return service.summary();}

    @GetMapping("/alerts")
    List<AlertView> alerts(){return jdbc.query("select e.trace_id,r.code,e.metric_code,e.observed_value,e.sample_count,e.threshold_value,e.severity,e.delivery_adapter,e.delivery_status,e.delivery_error_code,e.created_at from ops_alert_event e join ops_alert_rule r on r.id=e.rule_id order by e.created_at desc fetch first 200 rows only",(rs,n)->new AlertView(rs.getString(1),rs.getString(2),rs.getString(3),rs.getDouble(4),rs.getInt(5),rs.getDouble(6),rs.getString(7),rs.getString(8),rs.getString(9),rs.getString(10),rs.getObject(11,java.time.OffsetDateTime.class)));}

    public record AlertView(String traceId,String ruleCode,String metricCode,double observedValue,int sampleCount,
                            double thresholdValue,String severity,String deliveryAdapter,String deliveryStatus,
                            String deliveryErrorCode,java.time.OffsetDateTime createdAt){}
}
