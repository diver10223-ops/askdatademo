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
import java.util.Map;

@RestController
@RequestMapping("/api/v2/execution")
public class PlatformExecutionController {
    private final ExecutionClient executionClient;
    private final PlatformExecutionService executionService;

    public PlatformExecutionController(ExecutionClient executionClient, PlatformExecutionService executionService) {
        this.executionClient = executionClient;
        this.executionService = executionService;
    }

    @GetMapping("/health")
    String health() {
        return executionClient.health();
    }

    @PostMapping("/queries")
    @ResponseStatus(HttpStatus.ACCEPTED)
    ExecutionAccepted submit(@RequestBody PlatformExecutionService.QueryCommand command,
                               @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey,
                               HttpServletRequest request) {
        var traceId = request.getAttribute(TraceIdFilter.ATTRIBUTE).toString();
        var key = idempotencyKey == null || idempotencyKey.isBlank() ? UUID.randomUUID().toString() : idempotencyKey;
        return executionService.submit(command, traceId, key);
    }

    @GetMapping("/queries/{requestId}")
    Map<String,Object> detail(@org.springframework.web.bind.annotation.PathVariable UUID requestId,HttpServletRequest request){
        return executionService.detail(requestId,request.getAttribute(TraceIdFilter.ATTRIBUTE).toString());
    }
}
