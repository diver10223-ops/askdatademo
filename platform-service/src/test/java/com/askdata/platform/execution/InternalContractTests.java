package com.askdata.platform.execution;

import tools.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

class InternalContractTests {
    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    void javaConsumerSerializesEveryRequiredCommandField() throws Exception {
        var command = new ExecutionCommand(
                UUID.randomUUID(), UUID.randomUUID(), null, "user-1", List.of("analyst"),
                "贷款余额是多少？", "scenario-1", ExecutionCommand.ExecutionMode.POC,
                Map.of("orgIds", List.of("head-office")), "official-v1", null, 30_000
        );
        var serialized = mapper.valueToTree(command);
        var contract = mapper.readTree(Files.readString(Path.of("../contracts/internal-execution-v1.openapi.json")));
        var required = contract.at("/components/schemas/ExecutionCommand/required");
        for (var field : required) {
            assertThat(serialized.has(field.asText())).as(field.asText()).isTrue();
        }
        assertThat(serialized.get("executionMode").asText()).isEqualTo("POC");
    }

    @Test
    void frozenOperationsAndSecurityHeadersRemainPresent() throws Exception {
        var contract = mapper.readTree(Files.readString(Path.of("../contracts/internal-execution-v1.openapi.json")));
        assertThat(contract.path("openapi").asText()).startsWith("3.1");
        assertThat(contract.at("/components/securitySchemes/serviceToken/name").asText()).isEqualTo("X-Service-Token");
        assertThat(contract.at("/components/parameters/IdempotencyKey/name").asText()).isEqualTo("Idempotency-Key");
        assertThat(contract.at("/components/parameters/TraceId/name").asText()).isEqualTo("X-Trace-Id");
        assertThat(contract.path("paths").properties().stream().map(Map.Entry::getKey).collect(java.util.stream.Collectors.toSet()))
                .containsAll(Set.of("/internal/v1/executions", "/internal/v1/executions/{requestId}/events"));
    }
}
