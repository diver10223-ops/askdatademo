package com.askdata.platform.execution;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

@Component
public class ExecutionClient {
    private final RestClient client;
    private final String serviceToken;

    public ExecutionClient(@Value("${askdata.execution.base-url:http://127.0.0.1:8000}") String baseUrl,
                           @Value("${askdata.execution.service-token:askdata-local-service-token}") String serviceToken) {
        this.client = RestClient.builder()
                .requestFactory(new SimpleClientHttpRequestFactory())
                .baseUrl(baseUrl)
                .build();
        this.serviceToken = serviceToken;
    }

    public String health() {
        return client.get().uri("/internal/v1/health")
                .header("X-Service-Token", serviceToken)
                .retrieve().body(String.class);
    }

    public ExecutionAccepted submit(ExecutionCommand command, String traceId, String idempotencyKey) {
        return client.post().uri("/internal/v1/executions")
                .header("X-Service-Token", serviceToken)
                .header("X-Trace-Id", traceId)
                .header("Idempotency-Key", idempotencyKey)
                .body(command).retrieve().body(ExecutionAccepted.class);
    }
}
