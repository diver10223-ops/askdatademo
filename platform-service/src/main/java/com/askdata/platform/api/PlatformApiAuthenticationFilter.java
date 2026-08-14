package com.askdata.platform.api;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;

@Component
public class PlatformApiAuthenticationFilter extends OncePerRequestFilter {
    private final byte[] apiToken;

    public PlatformApiAuthenticationFilter(@Value("${askdata.security.api-token}") String apiToken) {
        this.apiToken = apiToken.getBytes(StandardCharsets.UTF_8);
        if (this.apiToken.length < 32) {
            throw new IllegalStateException("ASKDATA_PLATFORM_API_TOKEN must contain at least 32 bytes");
        }
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        var path = request.getRequestURI();
        return path.equals("/api/v2/health") || path.equals("/actuator/health")
                || (!path.startsWith("/api/v2/") && !path.startsWith("/actuator/"));
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        var authorization = request.getHeader("Authorization");
        var supplied = authorization != null && authorization.startsWith("Bearer ")
                ? authorization.substring(7).getBytes(StandardCharsets.UTF_8) : new byte[0];
        if (!MessageDigest.isEqual(apiToken, supplied)) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json");
            response.setCharacterEncoding(StandardCharsets.UTF_8.name());
            response.getWriter().write("{\"code\":\"UNAUTHENTICATED\",\"message\":\"平台API认证失败\",\"timestamp\":\""
                    + Instant.now() + "\"}");
            return;
        }
        chain.doFilter(request, response);
    }
}
