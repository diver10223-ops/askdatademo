package com.askdata.platform.identity;

import java.util.List;
import java.util.Map;

public interface IdentityProviderAdapter {
    String providerType();
    IdentityAssertion authenticate(String credential);

    record IdentityAssertion(String subject, String username, String displayName, String orgCode,
                             List<String> groups, Map<String, Object> attributes) {}
}
