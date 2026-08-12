package com.askdata.platform.execution;

import com.askdata.platform.api.TraceIdFilter;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;
import tools.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.UUID;
import java.util.Map;
import java.util.concurrent.TimeUnit;

@RestController
@RequestMapping("/api/v2/execution")
public class PlatformExecutionController {
    private static final List<String> TERMINAL_STATUSES = List.of(
            "WAITING_INPUT", "SHORT_CIRCUITED", "BLOCKED", "PARTIAL_SUCCESS",
            "SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT");
    private final ExecutionClient executionClient;
    private final PlatformExecutionService executionService;
    private final ObjectMapper mapper;

    public PlatformExecutionController(ExecutionClient executionClient, PlatformExecutionService executionService,
                                       ObjectMapper mapper) {
        this.executionClient = executionClient;
        this.executionService = executionService;
        this.mapper = mapper;
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

    @PostMapping("/queries/{requestId}/cancel")
    @ResponseStatus(HttpStatus.ACCEPTED)
    Map<String,Object> cancel(@org.springframework.web.bind.annotation.PathVariable UUID requestId,
                              @RequestHeader(value="Idempotency-Key",required=false)String key,
                              HttpServletRequest request){
        var actor = request.getUserPrincipal() == null ? "api-user" : request.getUserPrincipal().getName();
        return executionService.cancel(requestId,actor,key==null||key.length()<8?"cancel-"+requestId:key);
    }

    @GetMapping(value="/queries/{requestId}/events",produces=MediaType.TEXT_EVENT_STREAM_VALUE)
    StreamingResponseBody events(@org.springframework.web.bind.annotation.PathVariable UUID requestId,
                                 @RequestHeader(value="Last-Event-ID",defaultValue="0")long lastEventId){
        if (lastEventId < 0) throw new IllegalArgumentException("Last-Event-ID不能为负数");
        return output -> {
            long cursor = lastEventId;
            long heartbeat = System.nanoTime();
            output.write("retry: 1000\n\n".getBytes(StandardCharsets.UTF_8));
            output.flush();
            while (!Thread.currentThread().isInterrupted()) {
                var state = executionService.request(requestId);
                if (!TERMINAL_STATUSES.contains(state.status())) {
                    try { executionService.detail(requestId, state.traceId()); }
                    catch (RuntimeException ignored) { /* reconciler will retry; stream remains available */ }
                }
                var rows = executionService.events(requestId, cursor);
                for (var row : rows) {
                    cursor = row.eventId();
                    var data = mapper.writeValueAsString(Map.of(
                            "eventId", row.eventId(), "eventType", row.eventType(),
                            "requestId", requestId.toString(), "traceId", row.traceId(),
                            "occurredAt", row.createdAt().toString(),
                            "payload", mapper.readTree(row.payloadJson())));
                    output.write(("id: " + row.eventId() + "\nevent: " + row.eventType()
                            + "\ndata: " + data + "\n\n").getBytes(StandardCharsets.UTF_8));
                    output.flush();
                }
                state = executionService.request(requestId);
                if (TERMINAL_STATUSES.contains(state.status()) && rows.isEmpty()) break;
                if (System.nanoTime() - heartbeat > TimeUnit.SECONDS.toNanos(10)) {
                    output.write(": heartbeat\n\n".getBytes(StandardCharsets.UTF_8));
                    output.flush();
                    heartbeat = System.nanoTime();
                }
                try { Thread.sleep(250); }
                catch (InterruptedException exception) { Thread.currentThread().interrupt(); }
            }
        };
    }
}
