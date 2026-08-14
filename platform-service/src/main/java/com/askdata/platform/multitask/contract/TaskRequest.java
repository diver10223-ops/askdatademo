package com.askdata.platform.multitask.contract;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.UUID;

public record TaskRequest(
        @NotBlank @Pattern(regexp = "2\\.1") String schemaVersion,
        @NotNull UUID sessionId,
        UUID parentRequestId,
        @NotBlank @Size(max = 4000) String question,
        @Pattern(regexp = "MT0[1-8]") String scenarioCode,
        @NotNull @Valid Control control,
        @Min(1000) @Max(1800000) long timeoutMs) {

    public record Control(boolean previewPlan, boolean allowPartial) {}
}
