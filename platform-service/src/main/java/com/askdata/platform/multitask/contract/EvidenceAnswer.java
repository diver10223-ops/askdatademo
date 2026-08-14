package com.askdata.platform.multitask.contract;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.List;
import java.util.UUID;

public record EvidenceAnswer(@NotNull UUID requestId, @Min(1) int answerVersion,
                             @NotNull List<@Valid Claim> claims,
                             @NotNull List<@NotBlank String> unverifiedItems) {
    public record Claim(@Min(1) int claimNo, @NotBlank String text, @NotBlank String type,
                        boolean verified, @NotNull List<@NotNull UUID> factIds) {
        public Claim {
            if (verified && factIds.isEmpty()) {
                throw new IllegalArgumentException("verified claim requires evidence");
            }
        }
    }
}
