package com.askdata.platform.execution;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ExecutionCommand(
        UUID requestId,
        UUID sessionId,
        UUID parentRequestId,
        String subjectId,
        List<String> roleIds,
        String question,
        String scenarioId,
        ExecutionMode executionMode,
        Map<String, Object> permissionSnapshot,
        String configVersionId,
        String providerProfileId,
        int timeoutMs
) {
    public enum ExecutionMode { DEMO, POC, PRODUCTION }
}
