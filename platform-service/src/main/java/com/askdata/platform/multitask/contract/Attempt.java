package com.askdata.platform.multitask.contract;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;
import java.util.UUID;

public record Attempt(@NotNull UUID attemptId, @NotNull UUID taskId, @Min(1) int attemptNo,
                      @NotNull AttemptStatus status, String executionId, String errorCode,
                      Instant startedAt, Instant endedAt) {}
