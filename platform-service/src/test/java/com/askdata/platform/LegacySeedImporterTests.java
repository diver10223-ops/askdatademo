package com.askdata.platform;

import com.askdata.platform.seed.LegacySeedImporter;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
class LegacySeedImporterTests {
    @Autowired LegacySeedImporter importer;
    @Autowired JdbcTemplate jdbc;

    @Test
    void officialRuntimeFrontendAndLegacyResourcesImportIdempotently() throws Exception {
        var fixtures = Files.isDirectory(Path.of("../fixtures")) ? Path.of("../fixtures") : Path.of("fixtures");
        var first = importer.importDirectory(fixtures);
        var countsAfterFirst = counts();
        var second = importer.importDirectory(fixtures);
        var countsAfterSecond = counts();

        assertThat(first).isEqualTo(second);
        assertThat(first.roles()).isEqualTo(3);
        assertThat(first.scenarios()).isEqualTo(8);
        assertThat(first.cases()).isEqualTo(24);
        assertThat(first.turns()).isEqualTo(33);
        assertThat(first.legacyResources()).isEqualTo(5);
        assertThat(countsAfterSecond).isEqualTo(countsAfterFirst);
        assertThat(countsAfterSecond).containsExactly(3, 3, 3, 9, 3, 2, 8, 24, 24, 33, 4, 6);
        assertThat(jdbc.queryForObject("select count(*) from cfg_seed_import where source_code='official_baseline' and source_hash=?", Integer.class, first.baselineSha256())).isEqualTo(1);
        assertThat(jdbc.queryForObject("select count(*) from cfg_seed_import where source_code='frontend_baseline' and source_hash=?", Integer.class, first.baselineSha256())).isEqualTo(1);
        assertThat(jdbc.queryForObject("select count(*) from cfg_seed_import where source_code='runtime_defaults' and source_hash=?", Integer.class, first.runtimeSha256())).isEqualTo(1);
    }

    private int[] counts() {
        return new int[]{jdbc.queryForObject("select count(*) from iam_org where code like 'org-%'", Integer.class),
                count("iam_user"), count("iam_role"), count("iam_role_permission"), count("meta_metric"), count("meta_dimension"),
                count("flow_scenario"), count("flow_scenario_role"), count("flow_scenario_case"), count("flow_scenario_turn"),
                count("cfg_seed_import"), count("cfg_release_item")};
    }

    private int count(String table) {
        return jdbc.queryForObject("select count(*) from " + table, Integer.class);
    }
}
