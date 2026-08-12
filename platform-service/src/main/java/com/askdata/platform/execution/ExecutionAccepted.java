package com.askdata.platform.execution;

import java.util.UUID;

public record ExecutionAccepted(UUID requestId, Status status, String traceId, boolean idempotentReplay) {
    public enum Status { PENDING, CANCELLATION_REQUESTED, CANCELLED }
}
