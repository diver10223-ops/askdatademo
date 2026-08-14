package com.askdata.platform;

import com.askdata.platform.provider.ProviderManagementException;
import com.askdata.platform.provider.ProviderManagementService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.client.RestClient;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT, properties={
        "spring.datasource.url=jdbc:h2:mem:provider-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1",
        "askdata.provider.test-adapter-enabled=true"
})
class ProviderManagementTests {
    @LocalServerPort int port;
    @Autowired ProviderManagementService service;
    @Autowired JdbcTemplate jdbc;

    @Test
    void managementApiNeverEchoesExternalSecretReference(){
        var response=RestClient.builder().baseUrl("http://127.0.0.1:"+port).defaultHeader("Authorization","Bearer askdata-test-platform-api-token-32-bytes-minimum").build().post().uri("/api/v2/admin/providers/secrets")
                .contentType(MediaType.APPLICATION_JSON)
                .body("{\"code\":\"api-key\",\"secretType\":\"MODEL_API_KEY\",\"providerType\":\"TEST\",\"externalReference\":\"test-ref://valid/api-secret\",\"keyVersion\":\"v1\"}")
                .retrieve().body(String.class);
        assertThat(response).contains("api-key","fingerprint").doesNotContain("test-ref","api-secret");
    }

    @Test
    void externalSecretsNeverAppearInPublicViewsAndEnableRequiresSuccessfulDiagnostics(){
        var secret=service.createSecret(new ProviderManagementService.SecretCommand("provider-key","MODEL_API_KEY","TEST","test-ref://valid/key-v1","v1"),0);
        assertThat(secret.toString()).doesNotContain("test-ref://valid/key-v1");
        assertThat(secret.keyVersion()).isEqualTo("v1");

        var model=service.createModel(new ProviderManagementService.ModelCommand("model","模型","TEST","test://ok/model","test-model",secret.id(),10,2048,List.of("CHAT","SQL_GENERATION")),0);
        assertThatThrownBy(()->service.enableModel("model",0)).isInstanceOf(ProviderManagementException.class).hasMessageContaining("诊断");
        assertThat(service.diagnoseModel("model",0).result()).isEqualTo("SUCCEEDED");
        assertThat(service.enableModel("model",0).status()).isEqualTo("ENABLED");

        var sourceSecret=service.createSecret(new ProviderManagementService.SecretCommand("source-key","DATABASE_PASSWORD","TEST","test-ref://valid/db-v1","v1"),0);
        var source=service.createDataSource(new ProviderManagementService.DataSourceCommand("source","数据源","POSTGRESQL","TEST","test://ok/db","warehouse","readonly",sourceSecret.id(),true,1000,10),0);
        assertThatThrownBy(()->service.enableDataSource("source",0)).isInstanceOf(ProviderManagementException.class).hasMessageContaining("诊断");
        assertThat(service.diagnoseDataSource("source",0).result()).isEqualTo("SUCCEEDED");
        assertThat(service.enableDataSource("source",0).status()).isEqualTo("ENABLED");

        var runtime=service.createRuntime(new ProviderManagementService.RuntimeCommand("runtime","运行",model.id(),source.id(),"POC"),0);
        assertThat(service.enableRuntime(runtime.code(),0).status()).isEqualTo("ENABLED");
        assertThatThrownBy(()->jdbc.update("insert into ai_runtime_profile(code,name,model_profile_id,data_source_id,execution_mode,fixture_fallback,status) values ('unsafe','Unsafe',?,?,'POC',true,'DRAFT')",model.id(),source.id()))
                .isInstanceOf(org.springframework.dao.DataIntegrityViolationException.class);
        service.revokeSecret("provider-key",0);
        assertThat(service.model("model").status()).isEqualTo("DISABLED");
        assertThat(service.runtime("runtime").status()).isEqualTo("DISABLED");
        assertThatThrownBy(()->service.enableModel("model",0)).isInstanceOf(ProviderManagementException.class).hasMessageContaining("不可用");

        assertThat(jdbc.queryForObject("select count(*) from audit_operation_log where action like '%MODEL_PROFILE' or action like '%SECRET_REFERENCE'",Integer.class)).isGreaterThanOrEqualTo(6);
        assertThat(jdbc.queryForObject("select count(*) from ai_model_capability where model_profile_id=?",Integer.class,model.id())).isEqualTo(2);
    }

    @Test
    void rotationKeepsOnlyFingerprintHistoryAndInvalidDiagnosticCannotEnable(){
        assertThatThrownBy(()->service.createSecret(new ProviderManagementService.SecretCommand("raw-key","MODEL_API_KEY","TEST","plaintext-secret","v1"),0))
                .isInstanceOf(ProviderManagementException.class).hasMessageContaining("秘密值");
        var secret=service.createSecret(new ProviderManagementService.SecretCommand("rotate-key","MODEL_API_KEY","TEST","test-ref://valid/old","v1"),0);
        var rotated=service.rotateSecret("rotate-key",new ProviderManagementService.RotateSecretCommand("test-ref://invalid/new","v2"),0);
        assertThat(rotated.revision()).isEqualTo(2);
        assertThat(jdbc.queryForObject("select count(*) from ai_secret_rotation_log",Integer.class)).isEqualTo(1);
        assertThat(jdbc.queryForObject("select count(*) from ai_secret_rotation_log where cast(from_fingerprint as varchar) like '%test-ref%' or cast(to_fingerprint as varchar) like '%test-ref%'",Integer.class)).isZero();
        service.createModel(new ProviderManagementService.ModelCommand("bad-model","坏模型","TEST","test://ok/model","m",secret.id(),10,100,List.of()),0);
        assertThat(service.diagnoseModel("bad-model",0).result()).isEqualTo("FAILED");
        assertThatThrownBy(()->service.enableModel("bad-model",0)).isInstanceOf(ProviderManagementException.class).hasMessageContaining("诊断");
    }
}
