package com.askdata.platform.seed;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.nio.file.Path;

@Component
@ConditionalOnProperty(name = "askdata.seed.enabled", havingValue = "true")
public class SeedImportRunner implements ApplicationRunner {
    private final LegacySeedImporter importer;
    private final Path directory;

    public SeedImportRunner(LegacySeedImporter importer, @Value("${askdata.seed.directory}") String directory) {
        this.importer = importer;
        this.directory = Path.of(directory).toAbsolutePath().normalize();
    }

    @Override
    public void run(ApplicationArguments args) throws Exception {
        importer.importDirectory(directory);
    }
}
