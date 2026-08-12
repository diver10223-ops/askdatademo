package com.askdata.platform;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties =
        "spring.datasource.url=jdbc:h2:mem:asset-api-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1")
class AssetManagementApiTests {
    @LocalServerPort int port;
    @Autowired JdbcTemplate jdbc;

    @Test
    void metricApiWritesAndReadsNormalizedTable() {
        var client = RestClient.create("http://127.0.0.1:" + port);
        var body = "{\"code\":\"net_profit\",\"name\":\"净利润\",\"businessDefinition\":\"税后净利润\",\"calculationExpression\":\"net_profit\",\"unit\":\"元\",\"aggregationType\":\"SUM\",\"classificationLevel\":\"SENSITIVE\",\"detailAllowed\":false}";
        var created = client.post().uri("/api/v2/admin/assets/metrics").contentType(MediaType.APPLICATION_JSON).body(body).retrieve().body(String.class);
        assertThat(created).contains("net_profit", "DRAFT", "SENSITIVE");
        assertThat(jdbc.queryForObject("select count(*) from meta_metric where code='net_profit' and status='DRAFT'", Integer.class)).isEqualTo(1);
        assertThat(client.get().uri("/api/v2/admin/assets/metrics").retrieve().body(String.class)).contains("net_profit");
        assertThat(jdbc.queryForObject("select count(*) from audit_operation_log where action='CREATE_METRIC'", Integer.class)).isEqualTo(1);

        assertThatThrownBy(() -> client.post().uri("/api/v2/admin/assets/metrics").contentType(MediaType.APPLICATION_JSON)
                .body(body.replace("net_profit", "INVALID CODE")).retrieve().toBodilessEntity())
                .isInstanceOf(HttpClientErrorException.class)
                .satisfies(error -> assertThat(((HttpClientErrorException) error).getStatusCode().value()).isEqualTo(422));
    }
}
