package com.askdata.platform.provider;

public interface ProviderDiagnosticAdapter {
    String providerType();
    DiagnosticResult diagnoseModel(ModelProbe probe, String externalSecretReference);
    DiagnosticResult diagnoseDataSource(DataSourceProbe probe, String externalSecretReference);

    record ModelProbe(String endpoint, String modelName, double timeoutSeconds) {}
    record DataSourceProbe(String endpoint, String databaseName, String username, double timeoutSeconds) {}
    record DiagnosticResult(boolean succeeded, String code, String message, long latencyMs) {}
}
