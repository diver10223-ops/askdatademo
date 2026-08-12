package com.askdata.platform.api;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.UUID;

@Component
public class TraceIdFilter extends OncePerRequestFilter {
    public static final String HEADER = "X-Trace-Id";
    public static final String ATTRIBUTE = TraceIdFilter.class.getName() + ".traceId";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        var incoming = request.getHeader(HEADER);
        var traceId = incoming != null && incoming.matches("[A-Za-z0-9._:-]{1,128}")
                ? incoming : UUID.randomUUID().toString();
        MDC.put("traceId", traceId);
        request.setAttribute(ATTRIBUTE, traceId);
        response.setHeader(HEADER, traceId);
        try {
            chain.doFilter(request, response);
        } finally {
            MDC.remove("traceId");
        }
    }
}
