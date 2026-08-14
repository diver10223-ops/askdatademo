package com.askdata.platform;

import com.askdata.platform.runtime.PlatformSessionService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.client.RestClient;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT,properties="spring.datasource.url=jdbc:h2:mem:flow-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1")
class FlowManagementTests {
    @LocalServerPort int port;
    @Autowired JdbcTemplate jdbc;
    @Autowired PlatformSessionService sessions;

    @Test
    void scenarioApiUsesNormalizedTableAndPublishedReleaseOnlyAffectsNewSessions(){
        var client=RestClient.builder().baseUrl("http://127.0.0.1:"+port).defaultHeader("Authorization","Bearer askdata-test-platform-api-token-32-bytes-minimum").build();
        var created=client.post().uri("/api/v2/admin/flows/scenarios").contentType(MediaType.APPLICATION_JSON)
                .body("{\"code\":\"profit-query\",\"name\":\"利润查询\",\"description\":\"测试\",\"terminalLayer\":\"L7\",\"fallbackPolicy\":\"NONE\",\"sortNo\":10}").retrieve().body(String.class);
        assertThat(created).contains("profit-query","DRAFT");
        assertThat(jdbc.queryForObject("select count(*) from flow_scenario where code='profit-query'",Integer.class)).isEqualTo(1);

        jdbc.update("insert into iam_org(code,name,org_type,path,level_no,status) values ('org','Org','HEAD_OFFICE','/org',0,'ENABLED')");
        var org=jdbc.queryForObject("select id from iam_org where code='org'",Long.class);
        jdbc.update("insert into iam_user(public_id,username,display_name,user_type,org_id,identity_provider_code,external_subject,status) values ('u','u','U','BUSINESS',?,'test','u','ENABLED')",org);
        var user=jdbc.queryForObject("select id from iam_user where public_id='u'",Long.class);
        jdbc.update("insert into cfg_release(release_no,name,status,snapshot_json,snapshot_hash) values ('r1','R1','PUBLISHED','{}',?)","1".repeat(64));
        jdbc.update("insert into cfg_release(release_no,name,status,snapshot_json,snapshot_hash) values ('r2','R2','PUBLISHED','{}',?)","2".repeat(64));
        var r1=jdbc.queryForObject("select id from cfg_release where release_no='r1'",Long.class);
        var r2=jdbc.queryForObject("select id from cfg_release where release_no='r2'",Long.class);
        jdbc.update("insert into cfg_current_release(environment,release_id) values ('TEST',?)",r1);
        var oldSession=sessions.create(user,"TEST","DEMO");
        jdbc.update("update cfg_current_release set release_id=? where environment='TEST'",r2);
        var newSession=sessions.create(user,"TEST","DEMO");
        assertThat(oldSession.configReleaseId()).isEqualTo(r1);
        assertThat(sessions.find(oldSession.id()).configReleaseId()).isEqualTo(r1);
        assertThat(newSession.configReleaseId()).isEqualTo(r2);
    }
}
