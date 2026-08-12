CREATE TABLE audit_chain_head (
    chain_name VARCHAR(64) PRIMARY KEY,
    last_log_id BIGINT,
    last_hash CHAR(64) NOT NULL
);
INSERT INTO audit_chain_head(chain_name,last_log_id,last_hash) VALUES ('operation',NULL,'0000000000000000000000000000000000000000000000000000000000000000');

CREATE TABLE audit_integrity_chain (
    audit_log_id BIGINT PRIMARY KEY REFERENCES audit_operation_log(id),
    previous_hash CHAR(64) NOT NULL,
    payload_hash CHAR(64) NOT NULL,
    record_hash CHAR(64) NOT NULL UNIQUE,
    chained_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
