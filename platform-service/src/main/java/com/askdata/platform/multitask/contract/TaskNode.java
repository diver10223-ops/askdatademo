package com.askdata.platform.multitask.contract;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public record TaskNode(
        @NotNull UUID taskId,
        @NotBlank String code,
        @NotNull NodeType type,
        boolean critical,
        @NotNull NodeStatus status,
        @NotNull List<@NotBlank String> dependsOn,
        @NotNull Map<String, Object> input,
        @NotNull Map<String, Object> outputSchema,
        @Min(1000) @Max(1800000) long timeoutMs,
        @Min(1) @Max(10) int maxAttempts,
        @NotBlank String capabilityVersion) {

    public enum NodeType { SQL, CALCULATION, SUMMARY }
}
