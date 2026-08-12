package com.askdata.platform.provider;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name="askdata.provider.test-adapter-enabled", havingValue="true")
public class TestProviderDiagnosticAdapter implements ProviderDiagnosticAdapter {
    @Override public String providerType() { return "TEST"; }
    @Override public DiagnosticResult diagnoseModel(ModelProbe probe, String reference) { return result(probe.endpoint(), reference); }
    @Override public DiagnosticResult diagnoseDataSource(DataSourceProbe probe, String reference) { return result(probe.endpoint(), reference); }
    private DiagnosticResult result(String endpoint, String reference) {
        boolean ok=endpoint != null && endpoint.startsWith("test://ok") && reference != null && reference.startsWith("test-ref://valid");
        return new DiagnosticResult(ok, ok?"PROVIDER_OK":"PROVIDER_UNREACHABLE", ok?"诊断成功":"测试Provider拒绝连接", 1);
    }
}
