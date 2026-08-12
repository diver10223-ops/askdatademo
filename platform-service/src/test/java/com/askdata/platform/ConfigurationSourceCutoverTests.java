package com.askdata.platform;

import com.askdata.platform.configuration.ConfigurationSourceService;
import com.askdata.platform.flow.FlowManagementService;
import com.askdata.platform.seed.LegacySeedImporter;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.util.HexFormat;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(properties="spring.datasource.url=jdbc:h2:mem:cutover-test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1")
class ConfigurationSourceCutoverTests {
    @Autowired ConfigurationSourceService sources;
    @Autowired LegacySeedImporter importer;
    @Autowired FlowManagementService flows;
    @Autowired JdbcTemplate jdbc;
    @TempDir Path temporary;

    @Test
    void databaseIsOnlyWriteSourceAndLegacyFilesRemainImmutable() throws Exception {
        var fixtureDirectory=Path.of("../fixtures").toAbsolutePath().normalize();
        var baseline=fixtureDirectory.resolve("official_baseline_v1.json");
        var before=sha256(baseline);
        importer.importDirectory(fixtureDirectory);
        var importedAt=jdbc.queryForObject("select imported_at from cfg_seed_import where source_code='official_baseline'",java.time.OffsetDateTime.class);
        flows.create(new FlowManagementService.ScenarioCommand("db-only","数据库事实","兼容切换","L2","NONE",999),0);
        importer.importDirectory(fixtureDirectory);

        assertThat(sha256(baseline)).isEqualTo(before);
        assertThat(jdbc.queryForObject("select imported_at from cfg_seed_import where source_code='official_baseline'",java.time.OffsetDateTime.class)).isEqualTo(importedAt);
        assertThat(jdbc.queryForObject("select count(*) from flow_scenario where code='db-only'",Integer.class)).isEqualTo(1);
        var state=sources.current();
        assertThat(state.writeSource()).isEqualTo("DATABASE");
        assertThat(state.legacyWriteEnabled()).isFalse();
        assertThat(state.legacyReadEnabled()).isTrue();
        state=sources.disableLegacyRead(0);
        assertThat(state.stage()).isEqualTo("DB_ONLY_SEED_STANDBY");
        assertThat(state.legacyReadEnabled()).isFalse();
        assertThat(state.disasterSeedRetained()).isTrue();
        assertThat(sources.disableLegacyRead(0).version()).isEqualTo(state.version());
    }

    @Test
    void changedSeedCannotOverwriteImportedDatabase() throws Exception {
        var source=Path.of("../fixtures").toAbsolutePath().normalize();
        for(var name:new String[]{"official_baseline_v1.json","demo_runtime_defaults.json","legacy_admin_resources_v1.json"})
            Files.copy(source.resolve(name),temporary.resolve(name),StandardCopyOption.REPLACE_EXISTING);
        importer.importDirectory(temporary);
        Files.writeString(temporary.resolve("demo_runtime_defaults.json"),"{}");
        assertThatThrownBy(()->importer.importDirectory(temporary)).isInstanceOf(IllegalStateException.class).hasMessageContaining("禁止覆盖");
    }

    private String sha256(Path path)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));}
}
