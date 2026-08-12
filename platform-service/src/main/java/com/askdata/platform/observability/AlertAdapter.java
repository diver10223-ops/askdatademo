package com.askdata.platform.observability;

public interface AlertAdapter {
    String code();
    void send(AlertNotification notification);

    record AlertNotification(String traceId, String ruleCode, String metricCode, String severity,
                             double observedValue, double thresholdValue, int sampleCount) {}
}
