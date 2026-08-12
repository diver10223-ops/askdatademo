package com.askdata.platform.identity;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

@Component
@ConditionalOnProperty(name = "askdata.identity.test-provider-enabled", havingValue = "true")
public class TestIdentityProviderAdapter implements IdentityProviderAdapter {
    @Override
    public String providerType() {
        return "TEST";
    }

    @Override
    public IdentityAssertion authenticate(String credential) {
        if (credential == null || !credential.startsWith("test:")) {
            throw new IdentityAuthenticationException("测试身份凭据无效");
        }
        var subject = credential.substring("test:".length());
        if (subject.isBlank()) {
            throw new IdentityAuthenticationException("测试身份主体为空");
        }
        return new IdentityAssertion(subject, subject, "Test " + subject, "org-all", List.of("analysts"), Map.of("source", "test"));
    }
}
