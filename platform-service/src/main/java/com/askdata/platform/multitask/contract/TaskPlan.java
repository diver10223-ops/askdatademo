package com.askdata.platform.multitask.contract;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.util.List;
import java.util.UUID;

public record TaskPlan(
        @NotNull UUID planId,
        @NotNull UUID requestId,
        @Min(1) int planVersion,
        @NotNull PlanStatus status,
        @NotEmpty List<@Valid TaskNode> nodes,
        @NotNull List<@Valid Edge> edges,
        @NotBlank String completenessPolicy,
        @NotBlank String permissionSnapshotId,
        @NotBlank String configVersion,
        @NotBlank String createdBy,
        String confirmedBy) {

    public record Edge(@NotBlank String upstreamCode, @NotBlank String downstreamCode,
                       @NotNull DependencyType type) {}

    public enum DependencyType { SUCCESS, COMPLETION }
}
