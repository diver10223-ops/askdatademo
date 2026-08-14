package com.askdata.platform.api;

import jakarta.servlet.FilterChain;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

class PlatformApiAuthenticationFilterTests {
    private static final String TOKEN = "0123456789abcdef0123456789abcdef";

    @Test
    void failsStartupForWeakTokens() {
        assertThatThrownBy(() -> new PlatformApiAuthenticationFilter("short"))
                .isInstanceOf(IllegalStateException.class).hasMessageContaining("32 bytes");
    }

    @Test
    void protectsPlatformAndManagementEndpointsButLeavesHealthPublic() throws Exception {
        var filter = new PlatformApiAuthenticationFilter(TOKEN);
        var rejected = new MockHttpServletRequest("GET", "/api/v2/admin/observability/summary");
        var rejectedResponse = new MockHttpServletResponse();
        var rejectedChain = mock(FilterChain.class);
        filter.doFilter(rejected, rejectedResponse, rejectedChain);
        assertThat(rejectedResponse.getStatus()).isEqualTo(401);
        assertThat(rejectedResponse.getContentAsString()).contains("UNAUTHENTICATED");
        verifyNoInteractions(rejectedChain);

        var accepted = new MockHttpServletRequest("GET", "/api/v2/execution/health");
        accepted.addHeader("Authorization", "Bearer " + TOKEN);
        var acceptedResponse = new MockHttpServletResponse();
        var acceptedChain = mock(FilterChain.class);
        filter.doFilter(accepted, acceptedResponse, acceptedChain);
        verify(acceptedChain).doFilter(accepted, acceptedResponse);

        var health = new MockHttpServletRequest("GET", "/api/v2/health");
        assertThat(filter.shouldNotFilter(health)).isTrue();
    }
}
