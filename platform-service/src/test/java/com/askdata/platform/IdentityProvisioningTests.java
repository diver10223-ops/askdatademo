package com.askdata.platform;

import com.askdata.platform.identity.IdentityAuthenticationException;
import com.askdata.platform.identity.IdentityProvisioningService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(properties = {
        "askdata.identity.test-provider-enabled=true",
        "spring.datasource.url=jdbc:h2:mem:identity-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1"
})
class IdentityProvisioningTests {
    @Autowired JdbcTemplate jdbc;
    @Autowired IdentityProvisioningService identities;

    @Test
    void jitProvisioningIsIdempotentAndAuthenticationEventsAreAppendOnly() {
        jdbc.update("insert into iam_org(code,name,org_type,path,level_no,status) values ('org-all','All','HEAD_OFFICE','/org-all',0,'ENABLED')");
        jdbc.update("insert into iam_identity_provider(code,name,provider_type,jit_provisioning,status) values ('test-idp','Test','TEST',true,'ENABLED')");
        var first = identities.authenticate("test-idp", "test:alice", "127.0.0.1", "test-agent");
        var second = identities.authenticate("test-idp", "test:alice", "127.0.0.1", "test-agent");
        assertThat(second.userId()).isEqualTo(first.userId());
        assertThat(jdbc.queryForObject("select count(*) from iam_user where identity_provider_code='test-idp'", Integer.class)).isEqualTo(1);
        assertThat(jdbc.queryForObject("select count(*) from iam_external_identity", Integer.class)).isEqualTo(1);
        assertThat(jdbc.queryForObject("select count(*) from iam_user_auth_event where event_type='LOGIN'", Integer.class)).isEqualTo(2);

        jdbc.update("update iam_identity_provider set status='DISABLED' where code='test-idp'");
        assertThatThrownBy(() -> identities.authenticate("test-idp", "test:alice", null, null))
                .isInstanceOf(IdentityAuthenticationException.class).hasMessageContaining("未启用");
    }
}
