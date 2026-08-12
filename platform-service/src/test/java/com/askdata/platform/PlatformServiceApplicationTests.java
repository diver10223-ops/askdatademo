package com.askdata.platform;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.web.client.RestClient;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class PlatformServiceApplicationTests {
	@LocalServerPort
	int port;

	@Test
	void contextLoads() {
	}

	@Test
	void healthReportsProductAndSchemaVersion() {
		var body = RestClient.create("http://127.0.0.1:" + port)
				.get().uri("/api/v2/health").retrieve().body(String.class);
		assertThat(body).contains("\"status\":\"ok\"").contains("2.0.0-SNAPSHOT");
	}

}
