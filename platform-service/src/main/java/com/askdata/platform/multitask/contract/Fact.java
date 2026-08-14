package com.askdata.platform.multitask.contract;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record Fact(@NotNull UUID factId, @NotNull UUID taskId, @NotNull UUID attemptId,
                   Map<String, Object> payload, String storageUri,
                   @NotBlank @Pattern(regexp = "[0-9a-fA-F]{64}") String contentHash,
                   @Min(0) long rowCount, @NotBlank String dataAsOf,
                   @NotBlank String classificationLevel, @NotNull Instant expiresAt) {
    public Fact {
        if ((payload == null) == (storageUri == null || storageUri.isBlank())) {
            throw new IllegalArgumentException("exactly one of payload or storageUri is required");
        }
    }
}
