package com.askdata.platform.execution;

import com.askdata.platform.api.TraceIdFilter;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
@RequestMapping("/api/v2/execution")
public class PlatformExecutionController {
    private final ExecutionClient executionClient;

    public PlatformExecutionController(ExecutionClient executionClient) {
        this.executionClient = executionClient;
    }

    @GetMapping("/health")
    String health() {
        return executionClient.health();
    }

    @PostMapping("/simulate")
    @ResponseStatus(HttpStatus.ACCEPTED)
    ExecutionAccepted simulate(@RequestBody ExecutionCommand command,
                               @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey,
                               HttpServletRequest request) {
        var traceId = request.getAttribute(TraceIdFilter.ATTRIBUTE).toString();
        var key = idempotencyKey == null || idempotencyKey.isBlank() ? UUID.randomUUID().toString() : idempotencyKey;
        return executionClient.submit(command, traceId, key);
    }
}
