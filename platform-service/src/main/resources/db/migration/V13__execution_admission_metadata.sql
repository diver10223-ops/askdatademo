ALTER TABLE run_request ADD COLUMN queue_name VARCHAR(64) NOT NULL DEFAULT 'EXECUTION';
ALTER TABLE run_request ADD COLUMN queue_wait_ms BIGINT NOT NULL DEFAULT 0 CHECK (queue_wait_ms >= 0);
ALTER TABLE run_request ADD COLUMN queued_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE run_request ADD COLUMN admitted_at TIMESTAMP WITH TIME ZONE;
CREATE INDEX idx_run_request_queue_created ON run_request(queue_name,status,created_at,id);
