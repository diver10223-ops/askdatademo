package com.askdata.platform;

import com.askdata.platform.multitask.contract.*;
import jakarta.validation.Validation;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class MultitaskContractTests {
    @Test
    void taskRequestSchemaRejectsUnsupportedVersionAndTimeout() {
        try (var factory = Validation.buildDefaultValidatorFactory()) {
            var request = new TaskRequest("2.0", UUID.randomUUID(), null, "compare", "MT01",
                    new TaskRequest.Control(false, true), 999);
            assertThat(factory.getValidator().validate(request)).hasSize(2);
        }
    }

    @Test
    void stateMachinesAllowOnlyFrozenTransitions() {
        assertThat(StateTransitions.allows(PlanStatus.DRAFT, PlanStatus.VALIDATED)).isTrue();
        assertThat(StateTransitions.allows(PlanStatus.COMPLETED, PlanStatus.EXECUTING)).isFalse();
        assertThat(StateTransitions.allows(NodeStatus.RUNNING, NodeStatus.SUCCEEDED)).isTrue();
        assertThat(StateTransitions.allows(NodeStatus.SUCCEEDED, NodeStatus.READY)).isFalse();
        assertThat(StateTransitions.allows(AttemptStatus.PENDING, AttemptStatus.RUNNING)).isTrue();
        assertThat(StateTransitions.allows(RequestStatus.RUNNING, RequestStatus.PARTIAL_SUCCESS)).isTrue();
    }

    @Test
    void factRequiresExactlyOneStorageRepresentation() {
        assertThatThrownBy(() -> new Fact(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                Map.of(), "s3://duplicate", "0".repeat(64), 0, "2026-Q1", "INTERNAL", java.time.Instant.now()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void verifiedClaimRequiresEvidence() {
        assertThatThrownBy(() -> new EvidenceAnswer.Claim(1, "answer", "METRIC", true, java.util.List.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
