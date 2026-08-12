package com.askdata.platform.observability;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class LoggingAlertAdapter implements AlertAdapter {
    private static final Logger log = LoggerFactory.getLogger(LoggingAlertAdapter.class);

    @Override public String code() { return "logging"; }

    @Override
    public void send(AlertNotification alert) {
        log.warn("Operational alert traceId={} rule={} metric={} severity={} value={} threshold={} samples={}",
                alert.traceId(), alert.ruleCode(), alert.metricCode(), alert.severity(),
                alert.observedValue(), alert.thresholdValue(), alert.sampleCount());
    }
}
