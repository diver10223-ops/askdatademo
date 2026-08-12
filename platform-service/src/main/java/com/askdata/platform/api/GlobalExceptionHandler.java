package com.askdata.platform.api;

import jakarta.servlet.http.HttpServletRequest;
import com.askdata.platform.provider.ProviderManagementException;
import com.askdata.platform.execution.ExecutionAdmissionController;
import org.slf4j.MDC;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.Instant;

@RestControllerAdvice
public class GlobalExceptionHandler {
    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<ApiError> validation(MethodArgumentNotValidException exception) {
        var message = exception.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(error -> error.getField() + ": " + error.getDefaultMessage())
                .orElse("请求参数无效");
        return response(HttpStatus.UNPROCESSABLE_ENTITY, "INVALID_INPUT", message);
    }

    @ExceptionHandler(ProviderManagementException.class)
    ResponseEntity<ApiError> providerManagement(ProviderManagementException exception) {
        return response(HttpStatus.BAD_REQUEST, "PROVIDER_CONFIGURATION_INVALID", exception.getMessage());
    }

    @ExceptionHandler(ExecutionAdmissionController.OverloadedException.class)
    ResponseEntity<ApiError> overloaded(ExecutionAdmissionController.OverloadedException exception) {
        var status=exception.code().equals("EXECUTION_QUEUE_FULL")?HttpStatus.TOO_MANY_REQUESTS:HttpStatus.SERVICE_UNAVAILABLE;
        return response(status,exception.code(),exception.getMessage());
    }

    @ExceptionHandler(Exception.class)
    ResponseEntity<ApiError> unexpected(Exception exception, HttpServletRequest request) {
        // Exception messages and stack traces can contain SQL, provider URLs or driver values.
        // The client and operators correlate the safe exception type with the Trace ID instead.
        log.error("Unhandled API exception type={} traceId={}", exception.getClass().getSimpleName(), MDC.get("traceId"));
        return response(HttpStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "服务执行失败，请使用Trace ID联系管理员");
    }

    private ResponseEntity<ApiError> response(HttpStatus status, String code, String message) {
        return ResponseEntity.status(status).body(new ApiError(code, message, MDC.get("traceId"), Instant.now()));
    }
}
