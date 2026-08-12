CREATE TABLE cfg_source_state (
    singleton_id SMALLINT PRIMARY KEY CHECK (singleton_id = 1),
    stage VARCHAR(40) NOT NULL CHECK (stage IN ('DB_PRIMARY_LEGACY_READ_ONLY','DB_ONLY_SEED_STANDBY')),
    write_source VARCHAR(20) NOT NULL CHECK (write_source = 'DATABASE'),
    legacy_read_enabled BOOLEAN NOT NULL,
    legacy_write_enabled BOOLEAN NOT NULL CHECK (legacy_write_enabled = FALSE),
    disaster_seed_retained BOOLEAN NOT NULL,
    version_no INTEGER NOT NULL DEFAULT 1,
    updated_by BIGINT,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO cfg_source_state(singleton_id,stage,write_source,legacy_read_enabled,legacy_write_enabled,disaster_seed_retained)
VALUES (1,'DB_PRIMARY_LEGACY_READ_ONLY','DATABASE',true,false,true);
