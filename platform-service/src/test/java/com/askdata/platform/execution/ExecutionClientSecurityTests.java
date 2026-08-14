package com.askdata.platform.execution;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ExecutionClientSecurityTests {
    @Test
    void refusesMissingStrengthInternalServiceTokens() {
        assertThatThrownBy(() -> new ExecutionClient("http://127.0.0.1:1", "too-short"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("at least 32 bytes");
        assertThatCode(() -> new ExecutionClient("http://127.0.0.1:1", "0123456789abcdef0123456789abcdef"))
                .doesNotThrowAnyException();
    }
}
